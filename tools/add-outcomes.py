#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Her laba "Bu lab ne ise yariyor" bolumu ekler.

NEDEN: lablar KONUYU anlatiyor ama ogrenciye iki seyi soylemiyor:

  - NEDEN bu konu? Gercek iste hangi derdi cozuyor? Ogrenci komutlari
    dogru yazip lab'i bitiriyor, ama "bunu ne zaman kullanacagim"
    sorusunun cevabi yok. Konu akilda kalmiyor cunku bir probleme
    baglanmamis.
  - NE YAPABILIR OLACAGIM? Lab'in sonunda kazanilan somut beceri.
    Bunu yazmak, lab'in kendi kapsamini da durustlestiriyor: "Jenkins
    ogrenmek" degil, "pipeline'i Jenkinsfile olarak depoda saklamak".

"Nasil" sorusunun cevabi zaten var ("Bu lab nasil isliyor" bolumu,
add-orientation.py). Bu betik "neden" ve "nicin"i ekliyor.

Icerik lab'a OZGU, bu yuzden sabit metin degil asagidaki tabloda
duruyor. Her lab icin EN ve TR birlikte yaziliyor - biri eklenip
digeri atlanirsa lint'in i18n/parity kontrolu zaten kirilir.

Bolum isaretle sarili, yani betik tekrar calistirilabilir ve metin
degisirse yeniden uretilir.

Calistirma:
  python _platform/tools/add-outcomes.py              # uygula
  python _platform/tools/add-outcomes.py --dry-run    # ne degisecek
  python _platform/tools/add-outcomes.py --track DevSecOps
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MARK = "<!-- outcomes:auto -->"
END = "<!-- /outcomes:auto -->"
ORIENT = "<!-- orientation:auto -->"

EN_BASLIK = "## Why this lab matters"
EN_SONRA = "**After this lab you will be able to:**"
TR_BASLIK = "## Bu lab ne işe yarıyor"
TR_SONRA = "**Bu labdan sonra şunları yapabileceksiniz:**"

# lab yolu -> {"en": (neden, [kazanimlar]), "tr": (...)}
ICERIK = {
    "images": {
        "en": (
            "Every container starts from an image, so the image is where your "
            "app's dependencies, configuration and attack surface are decided. "
            "Getting this wrong is expensive later: a bloated base image means "
            "slow deployments and hundreds of CVEs you inherited without asking.",
            [
                "write a Dockerfile and build an image from it",
                "explain the difference between `CMD` and `ENTRYPOINT`, and when each one gets in your way",
                "read an image's layers and say why two images with identical contents can have different IDs",
                "argue for pinning a version tag instead of `latest`",
            ],
        ),
        "tr": (
            "Her container bir imajdan başlıyor; yani uygulamanızın "
            "bağımlılıkları, yapılandırması ve saldırı yüzeyi imajda "
            "belirleniyor. Burada yapılan hata sonradan pahalıya patlıyor: "
            "şişkin bir taban imaj hem yavaş dağıtım hem de istemeden "
            "devraldığınız yüzlerce CVE demek.",
            [
                "Dockerfile yazıp ondan imaj derlemek",
                "`CMD` ile `ENTRYPOINT` farkını ve hangisinin ne zaman ayağınıza dolandığını anlatmak",
                "bir imajın katmanlarını okuyup, içeriği birebir aynı olan iki imajın neden farklı ID taşıdığını söylemek",
                "`latest` yerine sürüm etiketi sabitlemeyi savunmak",
            ],
        ),
    },
    "registries": {
        "en": (
            "Images only help you if other machines can get them. A registry is "
            "that distribution point - and in a real pipeline it is also the "
            "place where release history lives and where access control is "
            "enforced. Teams that skip this end up copying tar files around.",
            [
                "push and pull images using a registry account",
                "read an image reference and name every part of it",
                "run a private registry in a container and use it",
                "explain why an organisation would host its own registry instead of using Docker Hub",
            ],
        ),
        "tr": (
            "İmaj, ancak başka makineler ona ulaşabiliyorsa işinize yarıyor. "
            "Registry bu dağıtım noktası — ve gerçek bir pipeline'da aynı "
            "zamanda sürüm geçmişinin tutulduğu, erişim denetiminin "
            "uygulandığı yer. Bu adımı atlayan ekipler sonunda tar dosyası "
            "taşımaya başlıyor.",
            [
                "registry hesabıyla imaj göndermek ve çekmek",
                "bir imaj referansını okuyup her parçasının adını söylemek",
                "container içinde özel bir registry çalıştırıp kullanmak",
                "bir kurumun neden Docker Hub yerine kendi registry'sini barındırdığını açıklamak",
            ],
        ),
    },
    "multi-stage": {
        "en": (
            "Build tools and compilers do not belong in production. A multi-stage "
            "build lets one Dockerfile compile the app and then throw the "
            "toolchain away, so what ships is only the runtime. The size "
            "difference is not cosmetic - every tool you ship is something an "
            "attacker can use.",
            [
                "write a Dockerfile with separate build, test and runtime stages",
                "build a single stage on its own with `--target`",
                "show the size gap between an SDK image and the final image, and explain where it comes from",
                "say why a `scratch`-based image has no shell, and why that is a security feature",
            ],
        ),
        "tr": (
            "Derleme araçları ve derleyiciler üretimde işi olmayan şeyler. Çok "
            "aşamalı derleme, tek bir Dockerfile'ın uygulamayı derleyip araç "
            "zincirini çöpe atmasını sağlıyor; sevk edilen şey yalnızca "
            "çalışma ortamı oluyor. Boyut farkı süs değil — sevk ettiğiniz her "
            "araç, saldırganın kullanabileceği bir araç.",
            [
                "derleme, test ve çalışma aşamalarını ayıran bir Dockerfile yazmak",
                "`--target` ile tek bir aşamayı kendi başına derlemek",
                "SDK imajı ile son imaj arasındaki boyut farkını gösterip nereden geldiğini açıklamak",
                "`scratch` tabanlı bir imajda neden kabuk olmadığını ve bunun neden bir güvenlik özelliği olduğunu söylemek",
            ],
        ),
    },
    "compose-build": {
        "en": (
            "A real application is several images, and they have to be built the "
            "same way every time - on your laptop and on the build server. "
            "Compose lets one file describe all of them, and override files let "
            "the same definition produce a dev build and a release build without "
            "copy-pasting.",
            [
                "build every image in an application with one command",
                "pass build arguments and attach labels that trace an image back to its source commit",
                "layer override files to get different image tags from one build definition",
                "explain why CI builds and local builds should share the same Compose files",
            ],
        ),
        "tr": (
            "Gerçek bir uygulama birden çok imaj demek ve bunların her seferinde "
            "aynı şekilde derlenmesi gerekiyor — hem sizin dizüstünüzde hem "
            "derleme sunucusunda. Compose hepsini tek dosyada tarif etmenizi, "
            "override dosyaları da aynı tanımdan kopyala-yapıştır yapmadan hem "
            "geliştirme hem sürüm derlemesi üretmenizi sağlıyor.",
            [
                "bir uygulamadaki bütün imajları tek komutla derlemek",
                "derleme argümanı geçmek ve imajı kaynak commit'ine bağlayan etiketler eklemek",
                "override dosyalarını üst üste bindirip tek tanımdan farklı imaj etiketleri almak",
                "CI derlemeleriyle yerel derlemelerin neden aynı Compose dosyalarını paylaşması gerektiğini açıklamak",
            ],
        ),
    },
    "jenkins": {
        "en": (
            "Somebody has to run the build when code is pushed, and it should not "
            "be a person. Jenkins is the automation server you are most likely to "
            "meet in an existing organisation - often one nobody dares rebuild. "
            "Knowing how to define jobs as code is what makes that server "
            "replaceable.",
            [
                "run Jenkins in a container and sign in to it",
                "create a job through the UI and see why that approach does not scale",
                "write the same job as a declarative pipeline",
                "store the pipeline in source control so the server holds no state you cannot recreate",
            ],
        ),
        "tr": (
            "Kod gönderildiğinde derlemeyi birinin çalıştırması gerekiyor ve bu "
            "bir insan olmamalı. Jenkins, mevcut bir kurumda karşınıza çıkma "
            "ihtimali en yüksek otomasyon sunucusu — çoğu zaman kimsenin "
            "yeniden kurmaya cesaret edemediği türden. İşleri kod olarak "
            "tanımlamayı bilmek, o sunucuyu değiştirilebilir kılan şey.",
            [
                "Jenkins'i container içinde çalıştırıp giriş yapmak",
                "arayüzden bir iş oluşturup bu yaklaşımın neden ölçeklenmediğini görmek",
                "aynı işi bildirimsel bir pipeline olarak yazmak",
                "pipeline'ı sürüm kontrolünde saklayarak sunucuda yeniden üretemeyeceğiniz hiçbir durum bırakmamak",
            ],
        ),
    },
    "pipeline": {
        "en": (
            "The point of containerised CI is that the build server needs nothing "
            "installed - no JDK, no .NET SDK, no Node. The build tools arrive in "
            "containers. That makes your pipeline portable and reproducible, and "
            "it is the pattern behind most modern CI systems.",
            [
                "run a build inside a container from a Jenkins pipeline",
                "use multi-stage builds so the pipeline compiles and packages in one step",
                "build a multi-image application with Compose from CI",
                "push the built images to a registry as part of the pipeline",
            ],
        ),
        "tr": (
            "Container tabanlı CI'ın bütün amacı, derleme sunucusunda hiçbir şeyin "
            "kurulu olmaması — ne JDK, ne .NET SDK, ne Node. Derleme araçları "
            "container içinde geliyor. Bu da pipeline'ınızı taşınabilir ve "
            "tekrarlanabilir yapıyor; modern CI sistemlerinin çoğunun "
            "arkasındaki desen bu.",
            [
                "Jenkins pipeline'ından container içinde derleme çalıştırmak",
                "çok aşamalı derlemeyle pipeline'ın tek adımda derleyip paketlemesini sağlamak",
                "CI'dan Compose ile çok imajlı bir uygulama derlemek",
                "derlenen imajları pipeline'ın parçası olarak registry'ye göndermek",
            ],
        ),
    },
    "prometheus": {
        "en": (
            "When something is slow at 3am you need numbers, not guesses. "
            "Prometheus is the de-facto metrics store in container platforms: it "
            "scrapes your apps on a schedule and keeps the history, so you can "
            "ask what the system looked like before it broke.",
            [
                "run Prometheus and point it at targets with a config file",
                "read the targets page and tell a scrape failure from an app failure",
                "query time-series data with PromQL",
                "explain the pull model and why it changes how you deploy apps",
            ],
        ),
        "tr": (
            "Gece üçte bir şey yavaşladığında tahmine değil sayılara ihtiyacınız "
            "olur. Prometheus, container platformlarında fiilî metrik deposu: "
            "uygulamalarınızı düzenli aralıklarla tarayıp geçmişi saklıyor, "
            "böylece sistem bozulmadan önce neye benzediğini sorabiliyorsunuz.",
            [
                "Prometheus'u çalıştırıp yapılandırma dosyasıyla hedeflere yöneltmek",
                "hedefler sayfasını okuyup tarama hatasıyla uygulama hatasını ayırmak",
                "PromQL ile zaman serisi verisi sorgulamak",
                "çekme (pull) modelini ve uygulamaları dağıtma biçiminizi neden değiştirdiğini açıklamak",
            ],
        ),
    },
    "prometheus/metrics": {
        "en": (
            "Prometheus can only store what your application publishes. Adding a "
            "metrics endpoint is a small code change with a large payoff: it turns "
            "'users say it is slow' into a number you can chart and alert on.",
            [
                "expose application metrics on an HTTP endpoint",
                "tell runtime metrics apart from the business metrics you add yourself",
                "pick a metric type (counter, gauge, histogram) that fits the question you are asking",
                "confirm Prometheus is collecting the new metric",
            ],
        ),
        "tr": (
            "Prometheus yalnızca uygulamanızın yayınladığını saklayabilir. Bir "
            "metrik ucu eklemek küçük bir kod değişikliği ama getirisi büyük: "
            "\"kullanıcılar yavaş diyor\" cümlesini grafiğe dökebileceğiniz ve "
            "alarm kurabileceğiniz bir sayıya çeviriyor.",
            [
                "uygulama metriklerini bir HTTP ucunda yayınlamak",
                "çalışma ortamı metrikleriyle kendi eklediğiniz iş metriklerini ayırt etmek",
                "sorduğunuz soruya uyan metrik tipini (counter, gauge, histogram) seçmek",
                "Prometheus'un yeni metriği topladığını doğrulamak",
            ],
        ),
    },
    "grafana": {
        "en": (
            "Metrics nobody looks at are metrics nobody acts on. A dashboard is "
            "how a team shares one picture of the system - and building one forces "
            "you to decide which numbers actually matter.",
            [
                "connect Grafana to Prometheus as a data source",
                "build panels from PromQL queries and choose a visualization that fits the data",
                "assemble panels into a dashboard that answers a specific question",
                "export a dashboard as JSON so it can live in source control",
            ],
        ),
        "tr": (
            "Kimsenin bakmadığı metrik, kimsenin harekete geçmediği metriktir. "
            "Dashboard, bir ekibin sisteme dair tek bir resmi paylaşma yolu — ve "
            "birini kurmak, hangi sayıların gerçekten önemli olduğuna karar "
            "vermenizi zorunlu kılıyor.",
            [
                "Grafana'yı veri kaynağı olarak Prometheus'a bağlamak",
                "PromQL sorgularından panel kurmak ve veriye uyan bir görselleştirme seçmek",
                "panelleri belirli bir soruyu yanıtlayan bir dashboard'da toplamak",
                "dashboard'u JSON olarak dışa aktarıp sürüm kontrolünde saklamak",
            ],
        ),
    },
    "elasticsearch": {
        "en": (
            "Metrics tell you something is wrong; logs tell you what happened. "
            "Once you have more than a handful of containers, `docker logs` stops "
            "working as a strategy - you need the logs collected in one searchable "
            "place that outlives the container.",
            [
                "run Elasticsearch and check it is healthy",
                "index documents and read them back",
                "search with the query API and understand how indices are organised",
                "explain why centralised logging matters more in containers than on servers",
            ],
        ),
        "tr": (
            "Metrikler bir şeyin ters gittiğini söyler; loglar ne olduğunu "
            "anlatır. Birkaç container'ı geçtiğinizde `docker logs` bir strateji "
            "olmaktan çıkıyor — logların, container'dan daha uzun yaşayan tek bir "
            "aranabilir yerde toplanması gerekiyor.",
            [
                "Elasticsearch'ü çalıştırıp sağlıklı olduğunu kontrol etmek",
                "belge indekslemek ve geri okumak",
                "sorgu API'siyle arama yapmak ve indekslerin nasıl düzenlendiğini anlamak",
                "merkezî loglamanın container'larda neden sunuculardakinden daha önemli olduğunu açıklamak",
            ],
        ),
    },
    "kibana": {
        "en": (
            "Searching logs with `curl` does not scale to an incident. Kibana is "
            "the front door to Elasticsearch: it is where you narrow millions of "
            "lines down to the twenty that explain the outage.",
            [
                "run Kibana against Elasticsearch with Logstash feeding it",
                "use the console to run queries directly",
                "search and filter across indices to isolate one request",
                "save a search and turn it into something the rest of the team can reuse",
            ],
        ),
        "tr": (
            "`curl` ile log aramak bir olay anında işe yaramıyor. Kibana, "
            "Elasticsearch'ün ön kapısı: milyonlarca satırı, kesintiyi açıklayan "
            "yirmi satıra indirdiğiniz yer.",
            [
                "Logstash besleyen bir kurulumda Kibana'yı Elasticsearch'e karşı çalıştırmak",
                "konsolu kullanarak doğrudan sorgu çalıştırmak",
                "indeksler arasında arayıp filtreleyerek tek bir isteği yalıtmak",
                "bir aramayı kaydedip ekibin geri kalanının yeniden kullanabileceği hale getirmek",
            ],
        ),
    },
    "tracing": {
        "en": (
            "In a distributed system the hard question is not 'is the API up' but "
            "'which of the eight calls behind this one request was slow'. Traces "
            "answer that, and they are the only pillar of observability that shows "
            "you the path through the system.",
            [
                "add trace exporting to an application",
                "follow a single transaction across more than one component",
                "explain context propagation and what breaks when a service drops the headers",
                "say when a trace is more useful than a log or a metric",
            ],
        ),
        "tr": (
            "Dağıtık bir sistemde zor soru \"API ayakta mı\" değil, \"bu tek "
            "isteğin arkasındaki sekiz çağrıdan hangisi yavaştı\". İzler bunu "
            "yanıtlıyor ve gözlemlenebilirliğin size sistemdeki yolu gösteren tek "
            "ayağı.",
            [
                "bir uygulamaya iz gönderimi eklemek",
                "tek bir işlemi birden çok bileşen boyunca takip etmek",
                "bağlam aktarımını ve bir servis başlıkları düşürdüğünde neyin bozulduğunu açıklamak",
                "bir izin ne zaman logdan ya da metrikten daha yararlı olduğunu söylemek",
            ],
        ),
    },
    "jaeger": {
        "en": (
            "Raw trace data is unreadable. Jaeger is where it becomes a picture: a "
            "waterfall that shows which span took the time. This is usually the "
            "fastest route from 'the system is slow' to a specific line of code.",
            [
                "run Jaeger and send application traces to it",
                "read a trace waterfall and find the slow span",
                "use tags to filter traces down to the ones you care about",
                "explain what a span is and how spans relate to each other",
            ],
        ),
        "tr": (
            "Ham iz verisi okunabilir değil. Jaeger onu bir resme çeviriyor: "
            "zamanı hangi span'in yediğini gösteren bir şelale. \"Sistem yavaş\" "
            "cümlesinden belirli bir kod satırına giden en hızlı yol genelde bu.",
            [
                "Jaeger'ı çalıştırıp uygulama izlerini ona göndermek",
                "iz şelalesini okuyup yavaş span'i bulmak",
                "etiketlerle izleri ilgilendiğiniz olanlara indirmek",
                "span'in ne olduğunu ve span'lerin birbiriyle ilişkisini açıklamak",
            ],
        ),
    },
    "static-analysis": {
        "en": (
            "The cheapest bug to fix is the one caught before it merges. Static "
            "analysis reads the source without running it and flags the patterns "
            "that turn into security advisories later. Wiring it into the build is "
            "what makes it stick - a report nobody reads changes nothing.",
            [
                "run SonarQube and analyse a project with it",
                "read the findings and tell a real problem from noise",
                "run the analysis as part of a Docker build",
                "set a quality gate that fails the build, so the check cannot be ignored",
            ],
        ),
        "tr": (
            "En ucuz hata, birleştirilmeden önce yakalanandır. Statik analiz "
            "kaynağı çalıştırmadan okuyup sonradan güvenlik bildirimine dönüşecek "
            "desenleri işaretliyor. Bunu derlemeye bağlamak kalıcı kılan şey — "
            "kimsenin okumadığı rapor hiçbir şeyi değiştirmiyor.",
            [
                "SonarQube'u çalıştırıp bir projeyi onunla analiz etmek",
                "bulguları okuyup gerçek sorunu gürültüden ayırmak",
                "analizi Docker derlemesinin parçası olarak çalıştırmak",
                "derlemeyi düşüren bir kalite kapısı kurup kontrolün atlanamaz olmasını sağlamak",
            ],
        ),
    },
    "scanning": {
        "en": (
            "You did not write most of the code in your image. The base layer and "
            "the libraries come with their own known vulnerabilities, and nobody "
            "tells you when a new one is published. Scanning is how you find out "
            "before somebody else does.",
            [
                "scan a container image and read the CVE report",
                "scan application dependencies as well as the OS layer",
                "scan Dockerfiles and Kubernetes manifests for misconfiguration",
                "judge which findings to act on, since a long list is not a plan",
            ],
        ),
        "tr": (
            "İmajınızdaki kodun çoğunu siz yazmadınız. Taban katman ve "
            "kütüphaneler kendi bilinen açıklarıyla geliyor ve yenisi "
            "yayımlandığında kimse size haber vermiyor. Tarama, bunu bir "
            "başkasından önce öğrenme yolunuz.",
            [
                "bir container imajını tarayıp CVE raporunu okumak",
                "işletim sistemi katmanının yanı sıra uygulama bağımlılıklarını da taramak",
                "Dockerfile ve Kubernetes manifestlerini yanlış yapılandırmaya karşı taramak",
                "hangi bulgulara göre hareket edeceğinize karar vermek — uzun bir liste plan değildir",
            ],
        ),
    },
    "golden-images": {
        "en": (
            "If every team picks its own base image, your organisation has no "
            "answer to 'which of our apps are affected by this CVE'. A curated set "
            "of approved base images turns that question into one you can answer, "
            "and one patch into a fix for everything built on it.",
            [
                "see the problem a free-for-all base image policy creates",
                "build a small library of golden images for one runtime",
                "rebuild applications on top of the golden images",
                "explain how the image cache and layer sharing make this cheap rather than wasteful",
            ],
        ),
        "tr": (
            "Her ekip kendi taban imajını seçerse, kurumunuzun \"bu CVE'den "
            "hangi uygulamalarımız etkileniyor\" sorusuna cevabı olmaz. Onaylı "
            "taban imajlardan oluşan düzenlenmiş bir küme, bu soruyu "
            "yanıtlanabilir hale getiriyor ve tek bir yamayı üzerine kurulan her "
            "şey için düzeltmeye çeviriyor.",
            [
                "serbest taban imaj politikasının yarattığı sorunu görmek",
                "tek bir çalışma ortamı için küçük bir altın imaj kütüphanesi derlemek",
                "uygulamaları altın imajların üzerine yeniden kurmak",
                "imaj önbelleği ve katman paylaşımının bunu nasıl israf değil ucuz kıldığını açıklamak",
            ],
        ),
    },
    "argo": {
        "en": (
            "Giving a build server cluster-admin credentials is how CI pipelines "
            "become the softest target in your infrastructure. GitOps inverts it: "
            "an agent inside the cluster pulls from Git, so nothing outside needs "
            "write access - and the repository becomes the record of what is "
            "actually deployed.",
            [
                "install ArgoCD into a cluster",
                "point an application at a Git repository and let ArgoCD deploy it",
                "watch a change in Git reach the cluster without anyone running `kubectl apply`",
                "explain why pull-based delivery is easier to secure than push-based",
            ],
        ),
        "tr": (
            "Derleme sunucusuna küme yöneticisi yetkisi vermek, CI pipeline'ını "
            "altyapınızın en yumuşak hedefi yapmanın yolu. GitOps bunu tersine "
            "çeviriyor: kümenin içindeki bir aracı Git'ten çekiyor, yani dışarıda "
            "hiçbir şeye yazma yetkisi gerekmiyor — ve depo, gerçekte neyin "
            "dağıtıldığının kaydı haline geliyor.",
            [
                "bir kümeye ArgoCD kurmak",
                "bir uygulamayı Git deposuna yöneltip dağıtımı ArgoCD'ye bırakmak",
                "Git'teki bir değişikliğin kimse `kubectl apply` çalıştırmadan kümeye ulaşmasını izlemek",
                "çekme temelli dağıtımın neden itme temellisinden daha kolay güvenlik altına alındığını açıklamak",
            ],
        ),
    },
    "admission": {
        "en": (
            "Policies written in a wiki get ignored. Admission control enforces "
            "them at the API server, before the workload exists - so 'no "
            "containers from untrusted registries' stops being a rule people "
            "remember and becomes a rule the cluster applies.",
            [
                "explain the difference between validating and mutating webhooks",
                "install OPA Gatekeeper into a cluster",
                "write a policy and watch the cluster reject a workload that breaks it",
                "weigh the risk that a broken admission webhook can block every deployment",
            ],
        ),
        "tr": (
            "Wiki'de yazan politikalar görmezden geliniyor. Giriş denetimi (admission "
            "control) onları API sunucusunda, iş yükü var olmadan önce uyguluyor — "
            "böylece \"güvenilmeyen registry'den container çalışmaz\" insanların "
            "hatırlaması gereken bir kural olmaktan çıkıp kümenin uyguladığı bir "
            "kurala dönüşüyor.",
            [
                "doğrulayan (validating) ve değiştiren (mutating) webhook farkını açıklamak",
                "bir kümeye OPA Gatekeeper kurmak",
                "politika yazıp kümenin onu çiğneyen bir iş yükünü reddetmesini izlemek",
                "bozuk bir giriş webhook'unun her dağıtımı durdurabileceği riskini tartmak",
            ],
        ),
    },
    "container-security": {
        "en": (
            "A container is not a security boundary by default. Out of the box your "
            "app runs as root, can write anywhere, and holds a token for the "
            "Kubernetes API it never needed. Each of those is a step an attacker "
            "skips if you leave it alone.",
            [
                "remove the service account token from Pods that do not call the API",
                "set CPU and memory limits and explain what happens without them",
                "run a container as a non-root user on a read-only filesystem",
                "recognise which of these controls will break a given application, and why Go and Java behave differently",
            ],
        ),
        "tr": (
            "Container varsayılan olarak bir güvenlik sınırı değil. Kutudan "
            "çıktığı haliyle uygulamanız root olarak çalışıyor, her yere "
            "yazabiliyor ve hiç ihtiyacı olmayan bir Kubernetes API token'ı "
            "taşıyor. Bunların her biri, siz dokunmazsanız saldırganın atlamak "
            "zorunda kalmadığı bir adım.",
            [
                "API'ye çağrı yapmayan Pod'lardan servis hesabı token'ını kaldırmak",
                "CPU ve bellek sınırı koymak ve bunlar olmadan ne olduğunu açıklamak",
                "bir container'ı salt okunur dosya sisteminde root olmayan kullanıcıyla çalıştırmak",
                "bu denetimlerden hangisinin hangi uygulamayı bozacağını ve Go ile Java'nın neden farklı davrandığını fark etmek",
            ],
        ),
    },
}


def blok(dil, veri):
    neden, kazanimlar = veri
    baslik = EN_BASLIK if dil == "en" else TR_BASLIK
    sonra = EN_SONRA if dil == "en" else TR_SONRA
    satirlar = [MARK, baslik, "", neden, "", sonra, ""]
    satirlar += ["- " + k for k in kazanimlar]
    satirlar += [END]
    return "\n".join(satirlar)


def uygula(yol, dil, veri, kuru):
    if not os.path.isfile(yol):
        return "yok"
    metin = io.open(yol, encoding="utf-8").read()
    yeni_blok = blok(dil, veri)

    desen = re.compile(re.escape(MARK) + r".*?" + re.escape(END), re.DOTALL)
    if desen.search(metin):
        yeni = desen.sub(lambda m: yeni_blok, metin, count=1)
        durum = "guncellendi"
    else:
        if ORIENT not in metin:
            return "orientation yok"
        yeni = metin.replace(ORIENT, yeni_blok + "\n\n" + ORIENT, 1)
        durum = "eklendi"

    if yeni == metin:
        return "degismedi"
    if not kuru:
        io.open(yol, "w", encoding="utf-8", newline="\n").write(yeni)
    return durum


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--track", default="DevSecOps")
    a = ap.parse_args()

    kok = os.path.join(ROOT, a.track, "labs")
    toplam = {}
    for slug, diller in sorted(ICERIK.items()):
        for dil, dosya in (("en", "README.md"), ("tr", "README.tr.md")):
            yol = os.path.join(kok, slug.replace("/", os.sep), dosya)
            d = uygula(yol, dil, diller[dil], a.dry_run)
            toplam[d] = toplam.get(d, 0) + 1
            print(f"  {slug:<22} {dil}  {d}")

    print()
    for k, v in sorted(toplam.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
