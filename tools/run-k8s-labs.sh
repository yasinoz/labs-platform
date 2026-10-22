#!/bin/bash
# Kubernetes lablarini gercekten uygulayip pod'larin ayaga kalkmasini bekler.
#
# NEDEN: "kubectl apply --dry-run" yalnizca semayi dogruluyor. Ogrencinin
# yasadigi sey farkli - imaj cekilemiyor, probe basarisiz oluyor, pod
# CrashLoopBackOff'a giriyor. Bu betik o asamayi test ediyor.
#
# ILK SURUMUN UC KUSURU VARDI, hepsi yanlis alarm uretiyordu:
#
#  1. Namespace'ler "--wait=false" ile siliniyordu. NodePort'lar KUME
#     KAPSAMLI; onceki labin Service'i henuz silinmeden sonraki lab
#     ayni portu (30010, 30020...) isteyince "provided port is already
#     allocated" aliniyordu. 10'dan fazla lab bu yuzden basarisiz
#     gorunuyordu. Artik silme tamamlanana kadar bekleniyor.
#
#  2. Alt dizinlerdeki DEGISKE spec'ler de uygulaniyordu. affinity gibi
#     lablarda bunlar tek tek denenmek icin duruyor ve bazilari kasitli
#     olarak Pending birakiyor; hepsini birden uygulamak catisma
#     uretiyor. Artik yalnizca specs/ altindaki ilk seviye uygulaniyor.
#
#  3. Helm chart dizinleri kubectl'e veriliyordu; onlar Go sablonu,
#     kubectl ayristiramiyor.
#
# Kullanim: bash _platform/tools/run-k8s-labs.sh <cikti-dosyasi> [lab...]
set -u
OUT="${1:-k8s-results.txt}"
shift || true
: > "$OUT"

# Tek basina uygulanamayan lablar:
#  - argo/operators/helm/productionizing: once CRD/operator kurulmali
#  - admission: KUME GENELI webhook kuruyor (OPA Gatekeeper, cert-manager).
#    Gatekeeper pod'lari hazir olmadan webhook devreye girince kumede
#    HICBIR namespace olusturulamiyor.
#  - clusters: k3d ile kendi cok kumeli ortamini kuruyor
#  - tools: metrics-server/dashboard gibi kume geneli bilesenler
#  - troubleshooting*: spec'ler KASITLI bozuk (alistirmanin kendisi)
SKIP="argo operators prometheus-operator helm productionizing admission clusters tools troubleshooting troubleshooting-2 troubleshooting-3"

LABS=("$@")
if [ ${#LABS[@]} -eq 0 ]; then
  mapfile -t LABS < <(ls -d Kubernetes/labs/*/ | xargs -n1 basename | sort)
fi

pass=0; fail=0; skip=0
for lab in "${LABS[@]}"; do
  case " $SKIP " in *" $lab "*) echo "SKIP  $lab" >> "$OUT"; skip=$((skip+1)); continue;; esac
  specs="Kubernetes/labs/$lab/specs"
  [ -d "$specs" ] || { echo "SKIP  $lab (specs yok)" >> "$OUT"; skip=$((skip+1)); continue; }

  # Yalnizca ilk seviye: alt dizinler degiske spec'ler.
  mapfile -t files < <(find "$specs" -maxdepth 1 -type f \( -name "*.yaml" -o -name "*.yml" \) \
                       ! -name "Chart.yaml" ! -name "values.yaml" ! -name "kustomization.yaml" | sort)
  if [ ${#files[@]} -eq 0 ]; then
    # Ilk seviyede dosya yoksa tek bir alt dizin sec (ilk alfabetik)
    sub=$(find "$specs" -mindepth 1 -maxdepth 1 -type d ! -name "*chart*" | sort | head -1)
    [ -n "$sub" ] && mapfile -t files < <(find "$sub" -maxdepth 1 -type f \( -name "*.yaml" -o -name "*.yml" \) | sort)
  fi
  [ ${#files[@]} -eq 0 ] && { echo "SKIP  $lab (uygulanacak spec yok)" >> "$OUT"; skip=$((skip+1)); continue; }

  ns="lab-$lab"
  kubectl create namespace "$ns" >/dev/null 2>&1

  if grep -lqE "^kind:[[:space:]]*Namespace" "${files[@]}" >/dev/null 2>&1; then
    NSARG=()
  else
    NSARG=(-n "$ns")
  fi

  # Her dosya kendi "-f" bayragini almali; tek -f'e birden fazla yol
  # vermek "Unexpected args" hatasi veriyor.
  FARGS=()
  for f in "${files[@]}"; do FARGS+=(-f "$f"); done

  if ! out=$(kubectl apply "${NSARG[@]}" "${FARGS[@]}" 2>&1); then
    echo "FAIL  $lab  (apply)" >> "$OUT"
    echo "$out" | grep -iE "error|invalid" | head -2 | sed 's/^/        /' >> "$OUT"
    fail=$((fail+1))
  else
    sleep 5
    if kubectl wait "${NSARG[@]:--n $ns}" --for=condition=Ready pod --all --timeout=180s >/dev/null 2>&1; then
      echo "OK    $lab" >> "$OUT"; pass=$((pass+1))
    else
      bad=$(kubectl get pods -n "$ns" --no-headers 2>/dev/null \
            | awk '$3!="Running" && $3!="Completed" {print "        "$1" "$3}' | head -3)
      if [ -z "$bad" ]; then
        echo "OK    $lab" >> "$OUT"; pass=$((pass+1))
      else
        echo "FAIL  $lab  (pod hazir degil)" >> "$OUT"; echo "$bad" >> "$OUT"; fail=$((fail+1))
      fi
    fi
  fi

  # BEKLEYEREK sil: NodePort'lar kume kapsamli, serbest kalmadan
  # sonraki lab ayni portu isteyip basarisiz oluyor.
  # Spec'ler KENDI namespace'lerini tanimliyorsa kaynaklar "lab-<ad>"
  # altinda degil, o adlarda olusuyor. Yalnizca lab-<ad>'i silmek
  # onlari geride birakiyor ve NodePort'lari tutmaya devam ediyorlar;
  # sonraki lab "already allocated" aliyor. Spec'lerdeki namespace
  # adlari da toplanip siliniyor.
  own=$(grep -hA2 -E "^kind:[[:space:]]*Namespace" "${files[@]}" 2>/dev/null         | grep -E "^[[:space:]]+name:" | awk '{print $2}' | tr -d '"' | sort -u)
  kubectl delete namespace "$ns" $own --ignore-not-found --timeout=180s >/dev/null 2>&1
  # Namespace silindikten SONRA da NodePort'un serbest kalmasi bir an
  # sürüyor; beklemeden sonraki lab ayni portu isteyip "already
  # allocated" aliyor.
  for _ in $(seq 1 20); do
    kubectl get svc -A -o jsonpath='{range .items[*]}{.spec.ports[*].nodePort}{"
"}{end}' 2>/dev/null       | grep -qE "30010|30020|30030|30040" || break
    sleep 2
  done
done

{
  echo "--- ozet ---"
  echo "OK   : $pass"
  echo "FAIL : $fail"
  echo "SKIP : $skip"
} >> "$OUT"
