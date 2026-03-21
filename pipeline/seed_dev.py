"""Generate a realistic local seed dataset for development without network access.

Creates diverse pre-2022 web documents across topics, years, and domains —
mimicking real web content from personal blogs, news, Wikipedia, HN, forums, etc.

Usage:
    python pipeline/seed_dev.py
    python pipeline/seed_dev.py --count 5000
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

SEED = 42
random.seed(SEED)

# ── Articles: each is UNIQUE — different topic, author voice, domain ────────────

ARTICLES = [
    # ── TECHNOLOGY ────────────────────────────────────────────────────────────
    {
        "domain": "towardsdatascience.com",
        "year_range": (2018, 2021),
        "content_type": "article",
        "url_slug": "understanding-machine-learning",
        "text": (
            "Machine learning has transformed how we build software. Rather than explicitly "
            "programming rules, we train models on data. Supervised learning requires labelled "
            "examples — you feed in (input, label) pairs and the model learns to predict labels "
            "from inputs. Linear regression predicts continuous values; logistic regression "
            "predicts binary classes; neural networks handle arbitrary mappings.\n\n"
            "The key challenge is generalization — performing well on unseen data. Overfitting "
            "occurs when a model memorizes training examples rather than learning patterns. "
            "Regularization techniques like L1/L2 penalties and dropout combat this. "
            "Cross-validation provides honest estimates of generalization performance.\n\n"
            "Tree-based models like XGBoost still outperform neural nets on tabular data in "
            "many benchmarks. They handle heterogeneous features and small datasets better. "
            "Always baseline with simple models before reaching for complexity."
        ),
    },
    {
        "domain": "blog.python.org",
        "year_range": (2020, 2021),
        "content_type": "article",
        "url_slug": "python-39-release-notes",
        "text": (
            "Python 3.9 introduces several quality-of-life improvements. Built-in collection "
            "types now support generic syntax — you can write list[int] and dict[str, int] "
            "directly without importing from typing. The new zoneinfo module brings IANA timezone "
            "support to the standard library, replacing the need for third-party pytz.\n\n"
            "Dictionary merge operators | and |= provide clean syntax for combining dicts. "
            "String methods removeprefix() and removesuffix() eliminate common boilerplate. "
            "Under the hood, CPython's parser was rewritten using PEG grammars, enabling better "
            "error messages and easier language evolution going forward.\n\n"
            "The CPython team also improved startup time and reduced memory usage in several "
            "common patterns. Python 3.9 dropped support for Python 2 compatibility shims "
            "that had accumulated over years of transition work."
        ),
    },
    {
        "domain": "docs.docker.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "understanding-docker-containers",
        "text": (
            "Containers package an application with its dependencies into a portable, isolated "
            "unit. Unlike virtual machines, containers share the host OS kernel — they're faster "
            "to start and use less memory. Docker popularized containers after its 2013 release, "
            "building on Linux kernel namespaces (isolation) and cgroups (resource limits).\n\n"
            "A Dockerfile describes how to build an image: start from a base image, copy code, "
            "install dependencies, specify the startup command. Images layer on top of each other, "
            "sharing unchanged layers — a Python 3.9 base image is downloaded once, not per "
            "application.\n\n"
            "Docker Compose orchestrates multi-container applications. For production at scale, "
            "Kubernetes provides scheduling, auto-scaling, and self-healing. But for most teams, "
            "Compose in production is simpler and sufficient. Don't add Kubernetes complexity "
            "before you actually need it."
        ),
    },
    {
        "domain": "stackoverflow.blog",
        "year_range": (2019, 2021),
        "content_type": "article",
        "url_slug": "rust-most-loved-language-again",
        "text": (
            "Rust has been Stack Overflow's most loved language for six consecutive years. "
            "The statistic is striking: 86% of Rust developers want to keep using it. The reason "
            "is memory safety without garbage collection — Rust's ownership system prevents "
            "entire classes of bugs at compile time: null pointer dereferences, buffer overflows, "
            "use-after-free, data races.\n\n"
            "The learning curve is real. Fighting the borrow checker frustrates newcomers. "
            "But developers who push through consistently report that the compiler's error "
            "messages teach good habits, and production Rust code simply doesn't crash in the "
            "ways C++ does. Mozilla's Servo browser engine, Dropbox's storage system, "
            "and Cloudflare's networking tools are production Rust success stories.\n\n"
            "The async story has matured with tokio reaching 1.0. WebAssembly is Rust's "
            "killer app for browser-adjacent code. Systems programming has a new language."
        ),
    },
    {
        "domain": "realpython.com",
        "year_range": (2018, 2021),
        "content_type": "article",
        "url_slug": "functional-programming-python",
        "text": (
            "Python is multi-paradigm — you can write procedurally, object-oriented, or "
            "functionally. Functional programming emphasizes pure functions (no side effects, "
            "deterministic output), immutable data, and function composition.\n\n"
            "Key Python FP tools: map() applies a function to every element; filter() selects "
            "elements matching a predicate; functools.reduce() folds a sequence to a single value. "
            "List comprehensions provide readable alternatives to map/filter. itertools provides "
            "lazy infinite sequences and combinatorial generators.\n\n"
            "functools.partial creates new functions by partially applying arguments. "
            "functools.lru_cache adds memoization with a one-liner. For complex pipelines, "
            "consider operator.pipe() or writing your own compose() utility. Functional code "
            "tends to be more testable: pure functions have no hidden state."
        ),
    },
    {
        "domain": "cs.stanford.edu",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "modern-cryptography-rsa-aes",
        "text": (
            "Modern cryptography rests on mathematical problems believed to be computationally "
            "hard. RSA relies on integer factorization: if N = p × q for large primes p and q, "
            "computing N is trivial but finding p and q from N is infeasible at 2048+ bit sizes.\n\n"
            "AES (Advanced Encryption Standard) is a symmetric block cipher using a "
            "substitution-permutation network over 10-14 rounds. No practical attack breaks "
            "AES-128 or AES-256. AES is used everywhere from TLS to disk encryption to "
            "file archival.\n\n"
            "Key exchange solves the bootstrap problem: how two parties establish a shared "
            "secret over an insecure channel. Diffie-Hellman (1976) solved this using the "
            "discrete logarithm problem. TLS 1.3 uses ECDHE — elliptic curve Diffie-Hellman "
            "ephemeral — providing forward secrecy: compromising today's keys doesn't reveal "
            "past sessions."
        ),
    },
    {
        "domain": "web.dev",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "web-vitals-core-metrics",
        "text": (
            "Google's Core Web Vitals define three measurable user experience metrics. "
            "Largest Contentful Paint (LCP) measures loading performance — how long until the "
            "largest visible element renders. Good LCP is under 2.5 seconds. First Input Delay "
            "(FID) measures interactivity — the delay between a user's first interaction and "
            "the browser's response. Cumulative Layout Shift (CLS) measures visual stability.\n\n"
            "Real-world LCP optimizations: preload critical fonts and hero images, eliminate "
            "render-blocking resources, use a CDN, serve modern image formats (WebP, AVIF). "
            "FID improvement focuses on reducing JavaScript execution time on the main thread — "
            "code-split aggressively, defer non-critical scripts, use web workers for heavy work.\n\n"
            "These metrics now directly influence Google Search ranking. Sites with poor Core "
            "Web Vitals face ranking penalties. The Chrome User Experience Report provides "
            "field data showing real user performance distributions."
        ),
    },
    {
        "domain": "netflixtechblog.com",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "chaos-engineering-netflix",
        "text": (
            "Netflix introduced Chaos Monkey in 2011 — a tool that randomly terminates "
            "production instances to ensure the system handles failures gracefully. The premise: "
            "failures are inevitable at scale, so it's better to deliberately cause them in "
            "controlled ways than to discover failure modes when they happen to real users.\n\n"
            "Chaos Engineering has evolved into a discipline. The Simian Army extended Chaos "
            "Monkey: Latency Monkey introduced artificial delays; Conformity Monkey shut down "
            "instances violating best practices; Security Monkey flagged insecure configurations. "
            "Chaos Kong simulated entire AWS availability zone failures.\n\n"
            "Key principles: define steady state behavior, hypothesize that it will continue "
            "under chaos, introduce realistic variables (instance failure, network latency, "
            "service unavailability), disprove the hypothesis by observing deviations. "
            "Always run experiments in production — staging rarely matches real traffic patterns."
        ),
    },
    {
        "domain": "martinfowler.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "microservices-tradeoffs",
        "text": (
            "Microservices decompose an application into small, independently deployable "
            "services, each owning its data and communicating over APIs. The promise: teams "
            "can develop, deploy, and scale services independently. Technology heterogeneity "
            "becomes possible — use the right tool for each service.\n\n"
            "The reality is more nuanced. Microservices introduce distributed systems "
            "complexity that doesn't exist in a monolith: network latency, partial failure, "
            "eventual consistency, distributed tracing. The operational overhead of running "
            "dozens of services — each with its own deployment pipeline, monitoring, and "
            "failure modes — is significant.\n\n"
            "My rule of thumb: don't start with microservices. Build a well-modularized "
            "monolith first. Extract services when a team boundary or scaling bottleneck "
            "makes it necessary. The seams between services should reflect Conway's Law — "
            "your system architecture will mirror your organization's communication structure."
        ),
    },
    {
        "domain": "blog.cloudflare.com",
        "year_range": (2018, 2021),
        "content_type": "article",
        "url_slug": "how-dns-works",
        "text": (
            "DNS is the internet's phone book, but most people don't think about how it works "
            "until it breaks. When you type google.com, your browser queries a recursive "
            "resolver (usually your ISP's or Google's 8.8.8.8). The resolver checks its cache; "
            "if not found, it walks the DNS hierarchy from root servers to TLD servers to "
            "authoritative name servers.\n\n"
            "The hierarchy: 13 root server clusters (operated by organizations including "
            "ICANN, Verisign, and NASA) know which servers handle .com, .org, .uk. TLD servers "
            "know the authoritative name servers for each domain. Authoritative servers hold "
            "the actual records: A records (IP addresses), MX records (mail servers), "
            "CNAME records (aliases), TXT records (SPF, DKIM, arbitrary data).\n\n"
            "DNSSEC adds cryptographic signatures to prevent cache poisoning attacks — "
            "without it, a malicious resolver can return forged records. DNS over HTTPS "
            "(DoH) encrypts DNS queries to prevent snooping, but shifts trust from your "
            "ISP to your DoH provider."
        ),
    },
    {
        "domain": "highscalability.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "database-sharding-strategies",
        "text": (
            "Database sharding distributes data across multiple database instances, each "
            "holding a subset (shard) of the total data. When a single database can't handle "
            "the write throughput or data volume, sharding is the horizontal scaling solution.\n\n"
            "Sharding strategies: range-based (rows 1-1M on shard 1, 1M-2M on shard 2) is "
            "simple but creates hotspots. Hash-based (shard = hash(user_id) % n) distributes "
            "evenly but makes range queries span all shards. Directory-based sharding uses a "
            "lookup table to map keys to shards, enabling flexible rebalancing at the cost "
            "of a single point of failure.\n\n"
            "The operational cost is real: cross-shard joins are expensive or impossible, "
            "distributed transactions require two-phase commit, rebalancing shards as data "
            "grows is complex. Many teams defer sharding longer than they think possible by "
            "vertically scaling and read replicas first. Pinterest, Discord, and Notion all "
            "published post-mortems on sharding migrations — worth reading before you start."
        ),
    },
    {
        "domain": "github.com/readme",
        "year_range": (2019, 2021),
        "content_type": "article",
        "url_slug": "open-source-sustainability",
        "text": (
            "Open source software powers the modern internet, yet the infrastructure it provides "
            "often runs on volunteer labor. The Log4Shell vulnerability in 2021 exposed this "
            "starkly: a critical library maintained by a small volunteer team was embedded in "
            "billions of deployments, yet had received essentially no financial support.\n\n"
            "Several funding models have emerged. GitHub Sponsors allows direct payments to "
            "maintainers. Open Collective provides fiscal hosting for projects to accept "
            "corporate donations transparently. Tidelift offers subscription-based support "
            "where companies pay for SLAs from maintainers. The Apache Software Foundation "
            "and Linux Foundation provide organizational infrastructure.\n\n"
            "The fundamental problem: companies extract enormous value from open source while "
            "contributing disproportionately little. A 2021 Harvard study found that the "
            "top 5% of open source packages by dependency count receive less than 1% of total "
            "open source funding. This isn't sustainable."
        ),
    },
    # ── SCIENCE ───────────────────────────────────────────────────────────────
    {
        "domain": "science.org",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "crispr-cas9-gene-editing",
        "text": (
            "CRISPR-Cas9 is a molecular scissors system that edits DNA with unprecedented "
            "precision. The Cas9 protein acts as the cutter; a guide RNA directs it to a "
            "specific 20-nucleotide sequence. When Cas9 cuts, the cell's repair machinery "
            "either disrupts the gene or inserts a template sequence.\n\n"
            "The 2020 Nobel Prize in Chemistry went to Jennifer Doudna and Emmanuelle "
            "Charpentier for developing CRISPR as an editing tool. Clinical trials are "
            "underway for sickle cell disease, beta-thalassemia, and several cancers. "
            "The first CRISPR-treated sickle cell patient, Victoria Gray, reported being "
            "pain-free for the first time in her adult life.\n\n"
            "Base editing and prime editing extend CRISPR without double-strand breaks, "
            "reducing off-target effects. Delivery remains the key challenge: lipid "
            "nanoparticles work for liver; AAV vectors for eyes; ex vivo editing for blood "
            "disorders. In vivo delivery to most tissues is still unsolved."
        ),
    },
    {
        "domain": "nature.com",
        "year_range": (2019, 2021),
        "content_type": "article",
        "url_slug": "james-webb-space-telescope",
        "text": (
            "The James Webb Space Telescope promises to revolutionize our understanding of "
            "the universe. JWST observes primarily in infrared, enabling it to see through "
            "dust clouds opaque to visible light and detect light from the most distant early "
            "galaxies, redshifted far beyond the visible spectrum.\n\n"
            "Its 6.5-meter primary mirror provides 7x the collecting area of Hubble. "
            "The sunshield, the size of a tennis court, keeps the telescope at −233°C. "
            "Orbiting at L2, 1.5 million km from Earth, it's beyond servicing missions "
            "but out of Earth's infrared glow.\n\n"
            "Priority science goals: observing the first galaxies after the Big Bang, "
            "characterizing exoplanet atmospheres for biosignatures, mapping star formation. "
            "Scientists expect JWST to answer questions we haven't yet thought to ask — "
            "as Hubble revealed dark energy through supernova observations, unanticipated."
        ),
    },
    {
        "domain": "climate.nasa.gov",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "greenhouse-effect-explained",
        "text": (
            "Earth's climate is governed by energy balance. The sun emits shortwave radiation; "
            "Earth absorbs it and re-emits longwave infrared. Greenhouse gases — CO2, methane, "
            "water vapor, nitrous oxide — absorb outgoing infrared and re-emit it in all "
            "directions, including back toward Earth's surface. This keeps Earth ~33°C warmer "
            "than it would otherwise be.\n\n"
            "Human activities have increased atmospheric CO2 from 280 ppm pre-industrial to "
            "over 410 ppm. Feedback mechanisms amplify this warming: melting ice reduces "
            "albedo, thawing permafrost releases methane, warming increases water vapor "
            "(itself a greenhouse gas). The IPCC AR6 concludes human influence has warmed "
            "the climate approximately 1.1°C above pre-industrial levels.\n\n"
            "Climate models have improved dramatically since the 1970s, correctly predicting "
            "stratospheric cooling, Arctic amplification, and shifted precipitation patterns. "
            "The physics is well-understood; the uncertainty is in feedback magnitudes and "
            "human emission trajectories."
        ),
    },
    {
        "domain": "quantumcomputing.stackexchange.com",
        "year_range": (2017, 2021),
        "content_type": "qa",
        "url_slug": "how-does-quantum-superposition-work",
        "text": (
            "Q: I've read that qubits can be 0 and 1 simultaneously. How does this actually "
            "work, and why can't we just read the value?\n\n"
            "A: Quantum superposition is often misrepresented. A qubit isn't secretly either "
            "0 or 1 until you look — it genuinely exists in a superposition of both states "
            "simultaneously, described by a probability amplitude for each outcome.\n\n"
            "The key is interference. A quantum algorithm manipulates probability amplitudes "
            "so that wrong answers cancel out (destructive interference) and the right answer "
            "reinforces (constructive interference). When you measure, you sample from the "
            "final amplitude distribution.\n\n"
            "This is why you can't just 'read' a qubit mid-computation — measurement collapses "
            "the superposition and destroys the quantum information. The art of quantum "
            "algorithm design is structuring the computation so the answer has high probability "
            "when you finally measure."
        ),
    },
    {
        "domain": "smithsonianmag.com",
        "year_range": (2013, 2019),
        "content_type": "article",
        "url_slug": "cambrian-explosion-lifes-big-bang",
        "text": (
            "Around 540 million years ago, animal life diversified explosively. Within roughly "
            "25 million years — a geological eyeblink — most animal phyla appeared. The Burgess "
            "Shale in British Columbia preserves extraordinary snapshots of Cambrian life: "
            "soft-bodied animals fossilized under unusual conditions.\n\n"
            "What triggered the explosion? Multiple factors: rising oxygen levels made complex "
            "animal metabolisms possible. The evolution of predation triggered an arms race — "
            "prey evolved eyes, shells, burrowing; predators evolved grasping appendages. "
            "Snowball Earth glaciations may have cleared ecological niches for rapid "
            "diversification afterward.\n\n"
            "The Cambrian fauna included strange animals. Opabinia had five eyes and a grasping "
            "proboscis. Anomalocaris was a meter-long apex predator. Hallucigenia's orientation "
            "confused early researchers so thoroughly that reconstructions put it upside down. "
            "Modern phylogenetics places these 'weird wonders' within established lineages."
        ),
    },
    {
        "domain": "sleepfoundation.org",
        "year_range": (2018, 2021),
        "content_type": "article",
        "url_slug": "science-of-sleep-why-we-dream",
        "text": (
            "Sleep occupies a third of human life, yet its function remains incompletely "
            "understood. NREM deep sleep is when growth hormone releases and memories "
            "consolidate, replaying hippocampal activity to transfer experiences to long-term "
            "cortical storage. REM sleep, when vivid dreaming occurs, is associated with "
            "emotional memory processing.\n\n"
            "Matthew Walker's research suggests REM strips emotional charge from memories — "
            "a form of overnight therapy. Sleep deprivation experiments show emotion "
            "recognition degrades dramatically after one poor night. The amygdala becomes "
            "60% more reactive to negative stimuli after 24 hours without sleep.\n\n"
            "Why do we dream? Activation-synthesis theory held that dreams are the cortex "
            "interpreting random brainstem signals. Threat simulation theory suggests dreams "
            "evolved to rehearse dangerous scenarios. The default mode network — active during "
            "mind-wandering — is highly active during REM, suggesting dreaming may simulate "
            "social interactions and perspective-taking."
        ),
    },
    {
        "domain": "cdc.gov",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "how-vaccines-build-immunity",
        "text": (
            "Vaccines train the immune system to recognize pathogens without causing disease. "
            "Traditional vaccines use killed or weakened pathogens or pathogen fragments. "
            "The immune system creates antibodies and memory B and T cells. On subsequent "
            "exposure, the immune response is faster and stronger — protective immunity.\n\n"
            "mRNA vaccines, first authorized for COVID-19, deliver mRNA instructions that "
            "cells translate into a pathogen protein (the SARS-CoV-2 spike). The immune "
            "system responds to this protein, building antibodies. The mRNA degrades within "
            "days and cannot integrate into DNA. This platform was decades in development.\n\n"
            "Herd immunity occurs when enough of a population is immune that transmission "
            "chains break spontaneously. The threshold depends on the pathogen's R0: measles "
            "(R0≈15) requires ~95% immunity; polio (R0≈5) requires ~80%. Delta and Omicron's "
            "higher transmissibility raised COVID's threshold substantially."
        ),
    },
    {
        "domain": "phys.org",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "dark-matter-what-we-know",
        "text": (
            "Dark matter constitutes approximately 27% of the universe's energy content, "
            "yet has never been directly detected. We infer its existence from multiple "
            "independent lines of evidence: galaxy rotation curves (stars orbit too fast "
            "at their distance from the galactic center), gravitational lensing (galaxy "
            "clusters bend more light than their visible mass predicts), and large-scale "
            "structure formation.\n\n"
            "The leading candidate is WIMPs — Weakly Interacting Massive Particles — "
            "predicted by supersymmetry. Despite exquisitely sensitive direct detection "
            "experiments (LUX, XENON1T, PandaX), no WIMP signal has been found. "
            "This absence has pushed constraints so tight that simple WIMP models are "
            "nearly ruled out.\n\n"
            "Alternatives: axions (ultralight particles), sterile neutrinos, primordial "
            "black holes. Modified Newtonian dynamics (MOND) attempts to explain rotation "
            "curves without dark matter but struggles with cosmological observations. "
            "The mystery remains one of physics' deepest open problems."
        ),
    },
    {
        "domain": "nih.gov",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "gut-microbiome-human-health",
        "text": (
            "The human gut contains roughly 38 trillion bacterial cells — approximately "
            "equal to the number of human cells in the body. This microbiome influences "
            "digestion, immune function, and increasingly appears connected to mental health "
            "through the gut-brain axis.\n\n"
            "The microbiome is shaped by diet, birth method, antibiotic use, and environment. "
            "Cesarean-born infants miss colonization with vaginal bacteria; formula-fed "
            "infants have different microbiomes than breastfed ones. These early differences "
            "associate with immune outcomes including allergy and asthma rates.\n\n"
            "Fecal microbiota transplant (FMT) has become a standard treatment for recurrent "
            "C. difficile infection — essentially resetting the gut microbiome using donor "
            "stool. Research into FMT for IBD, obesity, and depression is active but "
            "inconclusive. The field is early: we can sequence microbiomes easily but "
            "understanding what makes one 'healthy' remains contested."
        ),
    },
    # ── HISTORY / HUMANITIES ─────────────────────────────────────────────────
    {
        "domain": "historytoday.com",
        "year_range": (2014, 2020),
        "content_type": "article",
        "url_slug": "fall-of-roman-empire-causes",
        "text": (
            "No single cause explains Rome's fall — historians have proposed over 200 theories. "
            "Edward Gibbon blamed Christianity and barbarism. Modern historians identify a "
            "complex interplay: military overextension, economic stagnation, political "
            "instability, climate change, and pandemic.\n\n"
            "The Crisis of the Third Century (235-284 CE) saw 50 emperors in 50 years, "
            "civil war, economic collapse, and border pressure. The Antonine Plague and "
            "Plague of Cyprian each killed 5-10 million. Kyle Harper's 2017 work traces "
            "how climate and disease created vulnerabilities that political failures "
            "couldn't overcome.\n\n"
            "The traditional date of 476 CE, when Romulus Augustulus was deposed, marks "
            "the western empire's end. But Rome didn't fall — it transformed. The eastern "
            "empire continued as Byzantium until 1453, dying not with barbarian swords "
            "but with Ottoman cannons at the walls of Constantinople."
        ),
    },
    {
        "domain": "theatlantic.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "why-the-printing-press-changed-everything",
        "text": (
            "Gutenberg's press didn't just make books cheaper — it fundamentally rewired "
            "European society in ways its inventor could not have anticipated. Before printing, "
            "information was inherently scarce. A monastery might take months to copy a single "
            "manuscript. By 1500, roughly 20 million books had been printed.\n\n"
            "The Reformation is inseparable from the printing press. Luther's 95 Theses spread "
            "across Germany within weeks of their posting. Protestant translations of the Bible "
            "into vernacular languages — German, English, French — allowed individuals to read "
            "scripture without priestly mediation. Literacy rates climbed.\n\n"
            "The press also enabled the Scientific Revolution. Identical copies of "
            "Copernicus's tables could circulate simultaneously, allowing astronomers across "
            "Europe to work from the same data. Errors could be corrected at scale. "
            "The accumulation and distribution of knowledge accelerated beyond what any "
            "individual mind could previously absorb."
        ),
    },
    {
        "domain": "bbc.co.uk",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "cold-war-how-it-started",
        "text": (
            "The Cold War grew from World War II's strange alliance of necessity. The United "
            "States and Soviet Union cooperated to defeat Nazi Germany while harboring deep "
            "mutual suspicion. As Germany's defeat became inevitable, both powers maneuvered "
            "for postwar position. Soviet troops occupied Eastern Europe; American and British "
            "forces advanced from the west.\n\n"
            "The 1945 Yalta Conference shaped the postwar order. Roosevelt, Churchill, and "
            "Stalin divided Europe into spheres of influence. Stalin promised free elections "
            "in Eastern Europe; none were held. The Iron Curtain descended from the Baltic "
            "to the Adriatic.\n\n"
            "Nuclear weapons transformed the conflict's logic. Mutual Assured Destruction "
            "prevented direct superpower war — any conventional conflict risked escalating "
            "to nuclear exchange. Proxy wars in Korea, Vietnam, Angola, and Afghanistan "
            "became substitutes. The arms race consumed both economies; the Soviet "
            "economy's inefficiencies made it the more vulnerable."
        ),
    },
    {
        "domain": "newyorker.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "jazz-history-american-art-form",
        "text": (
            "Jazz emerged in New Orleans at the turn of the twentieth century from the "
            "collision of African rhythmic traditions, European harmony, blues feeling, "
            "and brass band music. It was, from the start, an improvisational music — "
            "musicians didn't read from a score so much as converse through their "
            "instruments, responding to each other in real time.\n\n"
            "Louis Armstrong's Hot Fives and Hot Sevens recordings (1925-1928) established "
            "that jazz could be high art. His phrasing, tone, and improvisational invention "
            "set a standard that shaped every subsequent musician. Miles Davis reinvented "
            "jazz at least three times: the cool jazz of 'Birth of the Cool,' the modal "
            "explorations of 'Kind of Blue,' the electric fusion of 'Bitches Brew.'\n\n"
            "Coltrane's 'A Love Supreme' (1964) pushed jazz toward the spiritual. "
            "Bill Evans's harmonic language influenced piano playing across genres. "
            "The music kept evolving while the recording industry moved on — jazz today "
            "lives in clubs, conservatories, and the ears of devotees who still find "
            "the conversation inexhaustible."
        ),
    },
    {
        "domain": "philosophybro.com",
        "year_range": (2013, 2020),
        "content_type": "blog",
        "url_slug": "trolley-problem-and-utilitarian-ethics",
        "text": (
            "The trolley problem has become the philosophy thought experiment everyone knows. "
            "A runaway trolley is heading toward five people tied to the tracks. You can "
            "pull a lever to divert it to a side track where it will kill one person. "
            "Do you pull the lever?\n\n"
            "Most people say yes. Then the footbridge variant: same five people, but you're "
            "on a bridge above the tracks. The only way to stop the trolley is to push a "
            "large man off the bridge onto the tracks, killing him but saving the five. "
            "Now most people say no — even though the arithmetic is identical.\n\n"
            "This inconsistency is philosophically fascinating. Utilitarian ethics says you "
            "should pull the lever and push the man — maximize welfare, minimize deaths. "
            "But our intuitions rebel against using a person as a means to an end. "
            "Judith Jarvis Thomson's work distinguishes doing harm from allowing harm, "
            "and using a person as a tool from incidentally causing their death. "
            "Decades of trolleyology later, we still disagree about why the cases feel different."
        ),
    },
    {
        "domain": "economicshelp.org",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "how-central-banks-control-inflation",
        "text": (
            "Central banks primarily control inflation through interest rates. When the "
            "Federal Reserve raises the federal funds rate, borrowing costs rise throughout "
            "the economy. Higher mortgage rates slow housing; higher corporate rates reduce "
            "investment; consumers save more and spend less. Aggregate demand falls, "
            "reducing inflationary pressure.\n\n"
            "The transmission mechanism works through multiple channels. The credit channel "
            "affects loan availability. The exchange rate channel: higher rates attract "
            "foreign capital, strengthening the currency and making imports cheaper. "
            "The expectations channel may be most powerful: if households and firms believe "
            "inflation will stay low, they negotiate accordingly — self-fulfilling expectations.\n\n"
            "The 2% inflation target emerged from 1990s New Zealand experiments. It provides "
            "room for nominal rates to fall during recessions (they can't go below zero), "
            "gives buffer against deflation, and accounts for measurement bias in price "
            "indices. Whether 2% is optimal is an active research question."
        ),
    },
    {
        "domain": "lithub.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "reading-slowly-in-the-age-of-distraction",
        "text": (
            "There's a case for reading that has nothing to do with information. You can "
            "get information faster from a summary, a podcast, a Wikipedia article. "
            "What a novel gives you that no summary can replicate is experience over time — "
            "the slow accumulation of a character's inner life, the way a writer's style "
            "becomes a kind of consciousness you temporarily inhabit.\n\n"
            "Nabokov called reading a physical act. He meant that you need to slow down "
            "enough to feel the sentences — to notice where the emphasis falls, why this "
            "word and not that one. Speed-reading sacrifices this. You can parse the "
            "information in Anna Karenina in an hour. You cannot have the experience.\n\n"
            "I've started putting my phone in another room when I read. Thirty minutes "
            "later, I'm surprised to find I've read forty pages. The attention that "
            "social media fragments is the same attention that makes reading deeply "
            "pleasurable. You have to choose which to feed."
        ),
    },
    # ── PERSONAL ESSAYS / BLOGS ───────────────────────────────────────────────
    {
        "domain": "paulgraham.com",
        "year_range": (2013, 2021),
        "content_type": "blog",
        "url_slug": "how-to-think-for-yourself",
        "text": (
            "One of the most important qualities a person can have is the ability to form "
            "their own opinions rather than adopting whatever views are currently fashionable. "
            "This is harder than it sounds. Most of us absorb opinions from our environment "
            "the way we absorb the local accent — gradually, without noticing.\n\n"
            "The question to ask is: what would I believe if I hadn't been exposed to "
            "this particular cultural milieu? What does the evidence actually support? "
            "This requires intellectual courage. The fashionable view is wrong surprisingly "
            "often — sometimes about small matters, sometimes about large ones.\n\n"
            "The way to develop independent thinking is to practice it on low-stakes "
            "questions first. Form strong opinions about things that don't matter socially — "
            "which programming language is better designed, which restaurant is better. "
            "Get used to disagreeing with consensus. Then you'll be better equipped when "
            "it matters."
        ),
    },
    {
        "domain": "waitbutwhy.com",
        "year_range": (2014, 2020),
        "content_type": "blog",
        "url_slug": "fermi-paradox-where-are-all-the-aliens",
        "text": (
            "The Fermi Paradox is named for physicist Enrico Fermi, who in 1950 asked a "
            "deceptively simple question during lunch: 'Where is everybody?' The Milky Way "
            "is 13.6 billion years old and contains 100-400 billion stars. Conservative "
            "estimates suggest millions of planets capable of supporting life. Even traveling "
            "at a small fraction of light speed, a civilization could colonize the entire "
            "galaxy in a few million years.\n\n"
            "So where are they? The Great Filter hypothesis suggests something is very "
            "hard — something filters civilizations into extinction or silence. The filter "
            "is either behind us (life is incredibly rare, or intelligent life is rare, "
            "or the jump to advanced civilization is extraordinarily difficult) or ahead of "
            "us (advanced civilizations destroy themselves, or there's something we "
            "haven't thought of).\n\n"
            "The most unsettling implication: if we find evidence of simple life on Mars, "
            "it would be terrible news. It would mean life is not rare — the filter is ahead."
        ),
    },
    {
        "domain": "simonwillison.net",
        "year_range": (2018, 2021),
        "content_type": "blog",
        "url_slug": "sql-for-the-web-developer",
        "text": (
            "After twenty years of web development, I'm convinced that most web developers "
            "are dramatically underusing SQL. ORMs are convenient but they're a leaky "
            "abstraction — when they generate inefficient queries, you need to understand "
            "SQL to fix them. And there are entire categories of questions that are trivial "
            "in SQL but awkward or impossible in ORM syntax.\n\n"
            "Window functions are transformative. Before I understood them, I'd write "
            "subqueries or fetch all the data and process in Python. Running totals, "
            "row rankings, moving averages, previous/next row values — all single queries "
            "with window functions. PARTITION BY divides the result set; ORDER BY controls "
            "the frame; ROWS BETWEEN defines exactly which rows to aggregate.\n\n"
            "CTEs (Common Table Expressions) are SQL's version of readable code. Instead "
            "of nested subqueries, you name intermediate results and compose them. "
            "Recursive CTEs traverse graphs and trees. Explain your queries, look at "
            "the execution plan, add indexes where the table scan hurts. SQL rewards time invested."
        ),
    },
    {
        "domain": "aaronswartz.com",
        "year_range": (2013, 2013),
        "content_type": "blog",
        "url_slug": "the-boy-who-could-change-the-world",
        "text": (
            "Information is power. But like all power, there are those who want to keep it "
            "for themselves. The entire scientific and cultural heritage of the world has "
            "been digitized and locked up by a handful of private corporations. Academic "
            "journal publishers charge enormous sums for the privilege of accessing the "
            "results of publicly-funded research.\n\n"
            "There is no justice in following unjust laws. If we don't follow laws against "
            "sharing knowledge, it's not because the law is wrong on all matters — it's "
            "because the specific law has been written by those who benefit from artificial "
            "scarcity, against the interests of those who could benefit from access.\n\n"
            "The internet has given us a rare opportunity to freely share knowledge. "
            "Wherever information has been locked up, we need to unlock it and share it "
            "with the world. We need to take information, wherever it is stored, and add "
            "it to the commons. With enough of us, around the world, sharing and acting, "
            "we can change the world."
        ),
    },
    {
        "domain": "kottke.org",
        "year_range": (2013, 2021),
        "content_type": "blog",
        "url_slug": "the-internet-is-full-of-people",
        "text": (
            "I've been running this website for over twenty years now. When I started in "
            "1998, there were maybe ten million people online. Now there are billions. "
            "The internet I started on felt intimate — you knew all the good sites, you "
            "could read everything worth reading. That's gone now, obviously.\n\n"
            "But something happened around 2012-2014 that was different from the growth "
            "before it. Twitter and Facebook had reached scale where they weren't just "
            "connecting people who were already on the internet — they were pulling in "
            "everyone, including people who had never engaged with anything like public "
            "discourse before. The result was... messy.\n\n"
            "I don't think the internet was ever the utopia the original techno-optimists "
            "imagined. But I still believe it was — and can be — something valuable. "
            "The original web was made by people with things to say, trying to reach "
            "other people. That impulse hasn't died. You just have to know where to look."
        ),
    },
    # ── FOOD / COOKING ────────────────────────────────────────────────────────
    {
        "domain": "seriouseats.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "the-food-lab-sous-vide-steak",
        "text": (
            "Sous vide has been a restaurant technique for decades, but affordable immersion "
            "circulators have brought it into home kitchens. The principle: seal food in a "
            "vacuum bag, cook it in a water bath held at precisely the target temperature. "
            "A steak cooked to 130°F for 2 hours will be 130°F all the way through — "
            "not the gradient you get from pan-searing.\n\n"
            "The science: proteins denature at different temperatures. Myosin (which makes "
            "meat tough) denatures around 120-130°F; actin (which makes meat dry) denatures "
            "around 150-165°F. Traditional cooking inevitably overcooks the outer layers "
            "while bringing the center up to temp. Sous vide eliminates this gradient.\n\n"
            "The catch: sous vide doesn't brown meat. You need a follow-up sear — ideally "
            "in a screaming hot cast iron pan or with a torch. Pat the steak completely dry "
            "before searing. The Maillard reaction (browning) requires surface temperatures "
            "above 280°F; water's evaporative cooling holds you below that until the surface "
            "dries. Dry surface = better crust."
        ),
    },
    {
        "domain": "bonappetit.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "how-to-make-perfect-pasta",
        "text": (
            "Italians will argue about pasta forever — egg versus no egg, bronze-die versus "
            "teflon-extruded, dry versus fresh. Here's what actually matters for making "
            "good pasta at home.\n\n"
            "Salt your water aggressively. The water should taste like the sea. This is "
            "your only chance to season the pasta itself; oil in the cooking water is "
            "a myth that does nothing useful. Use a large pot — pasta needs room to move.\n\n"
            "Finish cooking in the sauce. Pull pasta two minutes early and transfer directly "
            "to the pan with sauce, plus a cup of starchy pasta water. The starch in the "
            "water emulsifies with fat to create a silky, cohesive sauce that clings to the "
            "pasta rather than pooling at the bottom of the bowl. This is the secret that "
            "separates good pasta from great pasta. Toss aggressively over medium heat "
            "until the sauce is thick enough to coat."
        ),
    },
    {
        "domain": "eater.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "fermentation-revival-kimchi-kombucha",
        "text": (
            "Fermented foods have existed for as long as humans have — before refrigeration, "
            "fermentation was preservation. Kimchi, sauerkraut, miso, kefir, sourdough: "
            "each is a culture carrying centuries of accumulated microbial knowledge. "
            "The recent revival of home fermentation is partly food culture trend and "
            "partly genuine reconnection with lost techniques.\n\n"
            "The microbiology is fascinating. Lacto-fermentation doesn't require starter "
            "cultures — the lactic acid bacteria are already on the vegetables. Salt draws "
            "out moisture and creates an anaerobic environment that favors lactobacilli "
            "while inhibiting pathogens. The bacteria produce lactic acid, lowering pH, "
            "which both preserves the food and creates flavor.\n\n"
            "Kombucha is a fermented tea with a SCOBY — symbiotic culture of bacteria and "
            "yeast. The yeast converts sugar to alcohol and CO2; bacteria convert alcohol "
            "to acetic acid. Store-bought kombucha is often pasteurized, killing the live "
            "cultures. Home-brewed kombucha has live cultures, lower sugar, and tastes "
            "more complex."
        ),
    },
    # ── SPORTS ────────────────────────────────────────────────────────────────
    {
        "domain": "fivethirtyeight.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "analytics-revolution-basketball",
        "text": (
            "The analytics revolution in basketball started with a simple observation: "
            "the two-point jumper from mid-range is the NBA's worst shot. It's far enough "
            "that it misses often, but close enough that it's only worth two points. "
            "A three-pointer converts at lower rates but its extra point value makes it "
            "more efficient on expected value.\n\n"
            "This insight, propagated through Daryl Morey's Houston Rockets, changed how "
            "the league plays. Mid-range attempts dropped from about 40% of shots in 2001 "
            "to around 15% by 2019. Three-point attempts nearly doubled. The 2018-19 Rockets "
            "took roughly 50% of their shots from three and the rest at the rim.\n\n"
            "The counter-revolution has begun. Defenses adjusted, flooding the three-point "
            "line. Giannis Antetokounmpo and Joel Embiid showed that elite interior "
            "players can still dominate despite analytics. The 2021 Bucks won the title "
            "without being analytics-maximized. Context always complicates the equation."
        ),
    },
    {
        "domain": "theathletic.com",
        "year_range": (2018, 2021),
        "content_type": "article",
        "url_slug": "why-soccer-tactics-changed",
        "text": (
            "The dominant tactical trend in elite soccer over the past decade is pressing "
            "— aggressively winning back the ball high up the pitch, immediately after "
            "losing possession. Jürgen Klopp's gegenpressing ('counter-pressing') is its "
            "most famous incarnation. Liverpool under Klopp regularly recovered the ball "
            "within seconds of losing it, before the opponent could organize.\n\n"
            "Why does pressing work? It's hardest to build out from the back under pressure. "
            "Forced errors in dangerous areas lead to goals. The pressing team controls "
            "space without the ball. But pressing is physically demanding — it requires "
            "high fitness levels and coordinated team shape.\n\n"
            "Pep Guardiola's Manchester City took a different approach: positional play, "
            "controlling the ball in half-spaces, overloading zones to create numerical "
            "advantages. These philosophies are in productive tension — the teams that "
            "beat Klopp's Liverpool often bypassed the press with direct play through "
            "the defensive line."
        ),
    },
    # ── ECONOMICS / BUSINESS ─────────────────────────────────────────────────
    {
        "domain": "aswathdamodaran.com",
        "year_range": (2015, 2021),
        "content_type": "blog",
        "url_slug": "valuing-tech-companies",
        "text": (
            "Valuing technology companies has always made traditional analysts uncomfortable. "
            "The price-to-earnings approach breaks down when companies have no earnings, "
            "by design, for years. Amazon was unprofitable for most of its first decade; "
            "Uber and Lyft went public losing billions annually. What are they worth?\n\n"
            "The discounted cash flow model works in principle: the value of any business "
            "is the present value of future free cash flows. The challenge is the "
            "assumptions. Growth rates, margins, and discount rates that seem plausible "
            "individually compound into wildly different values depending on how optimistic "
            "you are about each input.\n\n"
            "I've learned to value technology companies by working backwards from "
            "the market price. At today's price, what growth rate and margin do you need "
            "to justify the valuation? Is that scenario plausible? This reveals the "
            "embedded assumptions without pretending we have more certainty than we do. "
            "The question isn't 'what is the right price?' but 'what story does this "
            "price tell, and do you believe it?'"
        ),
    },
    {
        "domain": "wsj.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "gig-economy-workers-rights",
        "text": (
            "The gig economy has created a classification problem that existing labor law "
            "wasn't designed to handle. Uber drivers and DoorDash couriers are officially "
            "independent contractors, which means they don't receive minimum wage guarantees, "
            "overtime pay, unemployment insurance, or employer contributions to Social Security.\n\n"
            "California's AB5 (2019) tried to reclassify many gig workers as employees, "
            "using the 'ABC test': a worker is an employee unless they are free from company "
            "control, doing work outside the company's normal business, and operating "
            "an independent business. Uber and Lyft spent over $200 million to pass "
            "Proposition 22, exempting app-based drivers.\n\n"
            "The underlying tension: companies get flexible workforce without employment costs; "
            "workers get flexibility without protections. The question is who should bear "
            "the economic risk of that flexibility. Traditional employment law assumed "
            "the employer. The gig model pushes it to the worker."
        ),
    },
    {
        "domain": "hbr.org",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "why-companies-fail",
        "text": (
            "Most companies fail not because they make obviously bad decisions, but because "
            "they optimize too well for their current environment. Blockbuster didn't ignore "
            "Netflix out of stupidity — Netflix's DVD-by-mail business was small and low-margin, "
            "and Blockbuster's best customers were in-store. Abandoning late fees would have "
            "destroyed the current business model to chase a speculative alternative.\n\n"
            "Clayton Christensen called this the innovator's dilemma. Disruptive technologies "
            "start worse than incumbents on traditional metrics — they're slower, less capable, "
            "less reliable. They serve non-consumers or low-end customers that incumbents "
            "don't value. Then they improve, and suddenly the incumbent's years of optimization "
            "are a liability.\n\n"
            "The implication is uncomfortable: rational management of a successful business "
            "naturally leads to its disruption. The only defense is creating internal "
            "units that cannibalize the core business before competitors do — which "
            "requires tolerating conflict between divisions and short-term profit sacrifice."
        ),
    },
    # ── ENVIRONMENT / NATURE ──────────────────────────────────────────────────
    {
        "domain": "nationalgeographic.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "ocean-acidification-coral-reefs",
        "text": (
            "The ocean absorbs roughly a quarter of human CO2 emissions annually. This "
            "absorption comes at a cost: when CO2 dissolves in seawater, it forms carbonic "
            "acid, lowering the ocean's pH. Since pre-industrial times, ocean surface pH "
            "has fallen from 8.2 to 8.1 — a 26% increase in acidity (pH is logarithmic).\n\n"
            "For calcifying organisms — corals, oysters, mussels, sea urchins — this "
            "acidification is critical. They build shells and skeletons from calcium carbonate, "
            "which dissolves more readily in acidic conditions. Coral larvae struggle to "
            "settle and grow; oyster hatcheries in the Pacific Northwest have already seen "
            "crop failures attributed to ocean acidification.\n\n"
            "The Great Barrier Reef has experienced three mass bleaching events since 2016. "
            "Bleaching occurs when water temperature rises above 1-2°C of the summer maximum — "
            "corals expel the symbiotic algae that give them color and 90% of their energy. "
            "Bleached corals can recover if temperatures return to normal quickly, but "
            "repeated bleachings leave them weakened and susceptible."
        ),
    },
    {
        "domain": "birdingworld.co.uk",
        "year_range": (2013, 2020),
        "content_type": "blog",
        "url_slug": "how-birds-navigate-migration",
        "text": (
            "A blackpoll warbler weighing 12 grams flies nonstop from the northeastern "
            "United States to South America — a journey of over 2,500 miles over the "
            "Atlantic Ocean, taking up to 90 hours without landing. How does it know "
            "where it's going?\n\n"
            "Birds navigate using multiple redundant systems. The sun compass reads the "
            "sun's position relative to the time of day, requiring an internal clock. "
            "The magnetic compass detects Earth's magnetic field through magnetite crystals "
            "in the beak or through light-dependent chemical reactions in the eye. "
            "Star patterns help calibrate direction during clear nights.\n\n"
            "Young birds on their first migration navigate by magnetic heading and distance — "
            "essentially following a genetically encoded vector. Experienced birds develop "
            "true navigation: they know where they are and where they're going, like GPS. "
            "How exactly they encode and recall geographic information remains an active "
            "research area."
        ),
    },
    # ── MUSIC ─────────────────────────────────────────────────────────────────
    {
        "domain": "pitchfork.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "streaming-changed-music-industry",
        "text": (
            "The music industry died in the 2000s and was reborn in the 2010s — but not "
            "for everyone. Napster and its successors destroyed album sales. iTunes saved "
            "digital music briefly. Spotify arrived in 2008 and gradually redefined how "
            "people listen: not ownership of recordings, but access to everything.\n\n"
            "Streaming is enormously convenient for listeners. It's genuinely terrible "
            "economics for most artists. A million streams on Spotify pays roughly $3,000-$4,000 "
            "— enough for a brief editorial mention on most music sites but not a living wage. "
            "The top 1% of artists capture the overwhelming majority of streams.\n\n"
            "What streaming changed more than anything is how music is structured. The "
            "chorus comes earlier. Songs are shorter. Albums matter less — playlists matter "
            "more. Skip rates after 30 seconds affect algorithmic recommendations. Music is "
            "being optimized for a mode of listening that rewards familiarity and "
            "frictionlessness over challenge and surprise."
        ),
    },
    {
        "domain": "musictheory.net",
        "year_range": (2013, 2020),
        "content_type": "article",
        "url_slug": "why-minor-keys-sound-sad",
        "text": (
            "The association between minor keys and sadness is real but culturally mediated. "
            "In Western music, minor scales have a lowered third scale degree relative to major — "
            "this interval difference (minor third versus major third above the root) creates "
            "a perceptibly different quality. Psychoacoustic research confirms that most "
            "listeners across cultures rate minor-key music as sadder.\n\n"
            "But the relationship isn't universal. Many non-Western musical traditions don't "
            "use the major/minor distinction at all. Turkish makamlar, Indian ragas, and "
            "Arabic maqamat use scales that don't map to Western major/minor. Some contain "
            "intervals smaller than a semitone. Emotional associations are learned within "
            "cultural context, not purely physical responses to sound.\n\n"
            "Within Western music, context dominates. 'Happy Birthday in a Minor Key' "
            "sounds haunting because we expect major. The Flinstones theme in minor becomes "
            "ominous. Our emotional responses to music are predictions based on learned "
            "expectations — the emotion comes from whether expectations are met or violated."
        ),
    },
    # ── PSYCHOLOGY / COGNITION ────────────────────────────────────────────────
    {
        "domain": "psychologytoday.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "cognitive-biases-explained",
        "text": (
            "Cognitive biases are systematic errors in how we think — not random mistakes "
            "but predictable patterns that affect judgment in consistent ways. The literature "
            "identifies dozens. A few are worth understanding in depth.\n\n"
            "Confirmation bias: we preferentially notice, remember, and seek information "
            "that confirms existing beliefs. We're not lying to ourselves; we're applying "
            "different standards of evidence to information we like (does this seem plausible?) "
            "versus information we dislike (prove it). This is why smart people can hold "
            "wrong beliefs confidently.\n\n"
            "The planning fallacy: we systematically underestimate how long tasks take, "
            "how much they'll cost, and what can go wrong. Reference class forecasting — "
            "asking how long similar projects took rather than reasoning from the current "
            "project's specifics — dramatically improves accuracy. The inside view (how our "
            "project looks to us) almost always looks better than the outside view "
            "(how it compares to similar projects)."
        ),
    },
    {
        "domain": "annualreviews.org",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "how-children-acquire-language",
        "text": (
            "Human children acquire language with remarkable speed and reliability. By age "
            "five, children have mastered the phonological, grammatical, and pragmatic "
            "systems of their native language — without explicit instruction, without "
            "access to negative evidence (parents rarely say 'that's wrong grammar'), "
            "and in wildly varying linguistic environments.\n\n"
            "Chomsky's Universal Grammar hypothesis proposes that humans are born with "
            "an innate language acquisition device — built-in knowledge of language "
            "structure that constrains what grammars children will consider. Statistical "
            "learning theorists counter that children are powerful pattern-learners who "
            "could acquire language without innate grammar, given sufficient input.\n\n"
            "The debate continues. Both sides agree that children are unusually good at "
            "certain language-learning tasks: rapid word learning (fast mapping), "
            "use of pragmatic cues to determine meaning (reading speaker intent), "
            "and generalization to novel structures. What remains unclear is how much "
            "of this is domain-specific language machinery versus general cognition."
        ),
    },
    # ── Q&A / DISCUSSION ──────────────────────────────────────────────────────
    {
        "domain": "news.ycombinator.com",
        "year_range": (2016, 2021),
        "content_type": "discussion",
        "url_slug": "ask-hn-best-technical-books",
        "text": (
            "Ask HN: What technical books genuinely changed how you think?\n\n"
            "Top comments:\n\n"
            "Structure and Interpretation of Computer Programs. I'd tried to read it "
            "three times before it clicked. When it did, I understood what programming "
            "is in a way I hadn't before. The core insight — that programs are data, "
            "and data can be programs — is obvious once you see it and invisible before.\n\n"
            "The Art of Problem Solving volumes. If you want to think mathematically, "
            "these books teach you how. Not theorems to memorize but habits of mind: "
            "how to draw the right diagram, when to work backwards, how to recognize "
            "structure across different-looking problems.\n\n"
            "Surely You're Joking, Mr. Feynman. Not technical in the narrow sense but "
            "it shows what genuine curiosity looks like. Feynman's approach — always "
            "asking why, always trying to derive things from first principles rather "
            "than accepting received wisdom — is a model for how to think.\n\n"
            "A Pattern Language by Christopher Alexander. About architecture but really "
            "about how to understand complex human systems. Christopher Alexander's "
            "influence on software design (design patterns, emergent complexity) is profound."
        ),
    },
    {
        "domain": "reddit.com",
        "year_range": (2015, 2021),
        "content_type": "discussion",
        "url_slug": "r-askscience-why-sky-blue",
        "text": (
            "Why is the sky blue? Explained for a five year old vs. explained technically.\n\n"
            "Simple version: Sunlight contains all the colors. As it travels through the "
            "atmosphere, it bumps into air molecules. Blue light bounces around much more "
            "than red light. So when you look at the sky, you see blue light that bounced "
            "toward your eyes from all directions.\n\n"
            "Technical version: Rayleigh scattering. The atmosphere is mostly nitrogen and "
            "oxygen molecules, much smaller than visible light wavelengths. Scattering "
            "intensity scales as 1/λ⁴ (lambda to the fourth power, where lambda is "
            "wavelength). Blue light (450nm) scatters about 5.5x more than red light (700nm). "
            "So blue light from the sun is scattered in all directions across the sky, "
            "while red and orange light travels more directly.\n\n"
            "Sunset explanation: at sunset, light travels through much more atmosphere. "
            "Blue light has scattered away; what reaches your eyes directly is the "
            "less-scattered red and orange. The same physics, opposite effect."
        ),
    },
    {
        "domain": "stackoverflow.com",
        "year_range": (2013, 2021),
        "content_type": "qa",
        "url_slug": "git-rebase-vs-merge",
        "text": (
            "Q: When should I use git rebase instead of git merge?\n\n"
            "A (accepted, 2847 upvotes): The short answer: use merge for shared branches, "
            "rebase for your own local work.\n\n"
            "Merge preserves history exactly as it happened. If three people worked on a "
            "feature branch and merged it to main, the history shows that — including all "
            "the commits, the divergence point, and the merge commit. This is accurate "
            "and auditable.\n\n"
            "Rebase rewrites history. git rebase main takes your commits and replays them "
            "on top of the current main, as if you'd started your branch from the current "
            "HEAD. The result is a clean, linear history. The cost: you've changed the "
            "commit hashes, so anyone who had your old branch will have conflicts.\n\n"
            "The golden rule of rebasing: never rebase commits that have been pushed to "
            "a shared repository. Rebase your local feature branch before creating a PR. "
            "Never rebase after others have pulled your branch."
        ),
    },
    {
        "domain": "quora.com",
        "year_range": (2014, 2021),
        "content_type": "qa",
        "url_slug": "what-made-apple-successful",
        "text": (
            "Q: What made Apple uniquely successful under Steve Jobs?\n\n"
            "A: Several factors, but they compound in important ways.\n\n"
            "First, Jobs had the rare combination of taste and conviction. Most executives "
            "optimize for what customers say they want. Jobs built what he thought they "
            "should want — often correctly. The iPhone killed the stylus (which carriers "
            "loved) and Flash (which web developers relied on) before alternatives existed.\n\n"
            "Second, Apple's integrated hardware-software model. When you control the full "
            "stack — silicon, operating system, applications — you can optimize the whole "
            "system rather than making each layer work with everyone else's layers. The M1 "
            "chip performance improvements happened because Apple could optimize the chip "
            "architecture for the exact software it needed to run.\n\n"
            "Third, Apple's willingness to cannibalize its own products. The iPhone "
            "destroyed iPod sales. The iPad hurt MacBook sales. Most companies protect "
            "revenue streams; Apple killed them before competitors could."
        ),
    },
    {
        "domain": "math.stackexchange.com",
        "year_range": (2013, 2021),
        "content_type": "qa",
        "url_slug": "why-is-pi-irrational",
        "text": (
            "Q: Why is π irrational? Is there an accessible proof?\n\n"
            "A: Johann Lambert proved π is irrational in 1761. The modern standard proof, "
            "due to Ivan Niven (1947), is remarkably short but requires calculus.\n\n"
            "The key idea: assume π = a/b for integers a, b. Construct a polynomial "
            "f(x) = x^n (a - bx)^n / n! which has special properties. Define "
            "F(x) = f(x) - f''(x) + f^(4)(x) - ... The key computation: "
            "(F'(x)sin(x) - F(x)cos(x))' = f(x)sin(x).\n\n"
            "Integrating from 0 to π: ∫f(x)sin(x)dx = F(0) + F(π), which must be an "
            "integer by the polynomial properties. But by choosing n large enough, "
            "the integral can be made smaller than 1 while remaining positive. "
            "The contradiction proves π cannot be rational.\n\n"
            "There's no getting around the fact that the proof requires seeing why "
            "these specific polynomials have these properties — that's where the "
            "creativity lies. Accessible doesn't mean easy."
        ),
    },
    {
        "domain": "physics.stackexchange.com",
        "year_range": (2013, 2021),
        "content_type": "qa",
        "url_slug": "what-is-entropy-really",
        "text": (
            "Q: I've heard entropy described as disorder, but that seems vague. What is "
            "entropy actually measuring?\n\n"
            "A: 'Disorder' is a pedagogical shorthand that creates more confusion than it "
            "resolves. Here's a cleaner way to think about it.\n\n"
            "Entropy measures the number of microscopic configurations (microstates) "
            "consistent with a given macroscopic state. Formally, S = k_B ln(Ω), where "
            "Ω is the number of microstates. A high-entropy state has many microscopic "
            "arrangements that look the same macroscopically; a low-entropy state has few.\n\n"
            "Why does entropy increase? Not because of any physical law that says it must, "
            "but because high-entropy states are overwhelmingly more probable. If you have "
            "10^23 gas molecules randomly bouncing around, the probability that they all "
            "happen to be in one corner of the room is astronomically small. "
            "The 'law' is really a statement about statistics at scale — there are so many "
            "more disordered states than ordered ones that any random evolution is "
            "overwhelmingly likely to move toward higher entropy."
        ),
    },
    # ── TRAVEL / CULTURE ──────────────────────────────────────────────────────
    {
        "domain": "lonelyplanet.com",
        "year_range": (2013, 2020),
        "content_type": "article",
        "url_slug": "tokyo-guide-for-first-time-visitors",
        "text": (
            "Tokyo rewards the traveler who stops trying to understand it and simply "
            "surrenders to the experience. Nothing quite prepares you for the scale — "
            "37 million people in the metropolitan area, train stations that are small "
            "cities, a convenience store culture so refined that 7-Eleven in Japan "
            "bears no resemblance to 7-Eleven anywhere else.\n\n"
            "The food is the reason most people come back. Not just sushi (though the "
            "sushi is transcendent) but ramen, tempura, yakitori, izakaya, tonkatsu, "
            "kaiseki. Neighborhoods specialize: Tsukiji for seafood, Shibuya for youth "
            "culture, Yanaka for old Tokyo preserved, Akihabara for electronics and manga.\n\n"
            "Learn to navigate the train system and Tokyo opens up. The Suica card works "
            "everywhere. The JR Yamanote line loops the central city. Subway lines fill "
            "in the grid. Google Maps understands the trains. The thing Western visitors "
            "find most disorienting isn't the language barrier — it's that Tokyo is "
            "quieter than any city of its size has a right to be."
        ),
    },
    {
        "domain": "nytimes.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "working-from-home-changing-cities",
        "text": (
            "The pandemic made remote work a mass experiment. Before 2020, roughly 5% "
            "of American workers worked from home full-time. By April 2020, it was over "
            "60% for white-collar workers. The infrastructure held — Zoom worked, Slack "
            "worked, email worked — and many companies discovered the office wasn't "
            "as essential as they'd assumed.\n\n"
            "The geographic consequences are only beginning to manifest. San Francisco "
            "and Manhattan saw significant outflows as workers realized they could live "
            "in Austin, Boise, or Raleigh while keeping California salaries. Housing "
            "prices in destination cities spiked; urban cores saw office vacancy rates "
            "hit records.\n\n"
            "What's being lost is harder to measure than what's gained. Remote work "
            "optimizes for explicit coordination — scheduled meetings, documented "
            "decisions. It struggles with implicit knowledge transfer, the hallway "
            "conversation where a senior engineer mentions something important off the "
            "cuff, the random collision that leads to an unexpected collaboration. "
            "We don't know yet which of these losses matter and which can be replicated."
        ),
    },
    # ── DATABASE / SYSTEMS ────────────────────────────────────────────────────
    {
        "domain": "db-engines.com",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "postgresql-vs-mysql",
        "text": (
            "PostgreSQL and MySQL are the two dominant open-source relational databases. "
            "Both implement SQL and ACID transactions, but they differ in philosophy.\n\n"
            "PostgreSQL prioritizes standards compliance and extensibility. It supports "
            "complex queries, window functions, CTEs, and JSON natively. The type system "
            "is extensible — custom types, operators, and index types. Full-text search, "
            "PostGIS for geospatial data, and JSONB make Postgres a generalist database.\n\n"
            "MySQL prioritizes read performance and simplicity. Under InnoDB (the default "
            "engine), it handles read-heavy workloads extremely well. MySQL has broader "
            "hosting support and simpler operational tooling. It historically lagged on "
            "features: window functions arrived in MySQL 8.0 (2018), CTEs too.\n\n"
            "Stack Overflow's 2021 survey showed PostgreSQL overtaking MySQL in developer "
            "preference for the first time. For new projects with complex query needs, "
            "Postgres is the modern default."
        ),
    },
    {
        "domain": "redis.io",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "redis-data-structures-explained",
        "text": (
            "Redis is often described as a key-value store, but that undersells it. "
            "Redis's power is its rich data structures. Strings are the basic type — "
            "useful for caching, counters (INCR is atomic), and simple session storage.\n\n"
            "Lists are linked lists — fast push/pop from either end. Use them for queues "
            "(RPUSH + BLPOP for a blocking consumer), activity feeds, or any FIFO structure. "
            "Sets store unordered unique values — great for tags, membership, set operations "
            "(union, intersection, difference). Sorted sets add a score to each member, "
            "enabling leaderboards, range queries by score, and rate limiting.\n\n"
            "Hashes store field-value pairs within a key — essentially a hash map within "
            "Redis. Use them to store object properties without serializing/deserializing "
            "the whole object when you only need one field. HyperLogLog provides "
            "approximate cardinality counting (unique visitor counts) using minimal memory. "
            "Pub/Sub enables lightweight message passing between processes."
        ),
    },
    {
        "domain": "linux.die.net",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "understanding-linux-file-permissions",
        "text": (
            "Linux file permissions confuse many newcomers. The ten characters in ls -l "
            "output (like -rwxr-xr--) encode type and permissions in a compact format.\n\n"
            "The first character is type: - for regular file, d for directory, l for "
            "symbolic link. The next nine are three triads of rwx: read, write, execute. "
            "First triad is owner permissions, second is group, third is other (everyone).\n\n"
            "chmod changes permissions. chmod 755 sets owner to rwx (4+2+1=7), group "
            "to r-x (4+0+1=5), other to r-x. chmod +x adds execute permission for all. "
            "chmod u+x adds execute only for owner. Directories need execute permission "
            "to be traversed — you can't cd into a directory without execute permission, "
            "even if you have read permission.\n\n"
            "chown changes ownership. chown user:group file. sudo is required to change "
            "ownership to another user. The root user bypasses all permission checks."
        ),
    },
    # ── MATHEMATICS ───────────────────────────────────────────────────────────
    {
        "domain": "math.mit.edu",
        "year_range": (2015, 2020),
        "content_type": "article",
        "url_slug": "linear-algebra-machine-learning",
        "text": (
            "Linear algebra is the mathematical backbone of machine learning. Data lives "
            "in high-dimensional vector spaces; models are functions over these spaces; "
            "training moves parameters along gradient vectors to minimize loss surfaces.\n\n"
            "A matrix represents a linear transformation. The eigenvectors of a matrix "
            "are directions unchanged by the transformation, only scaled by eigenvalues. "
            "PCA finds the eigenvectors of the data covariance matrix — directions of "
            "maximum variance — for dimensionality reduction.\n\n"
            "Neural networks are compositions of linear transformations (weight matrices) "
            "and nonlinear activations. Without nonlinearity, any deep network would "
            "collapse to a single matrix multiplication. The Universal Approximation "
            "Theorem states a network with sufficient neurons can approximate any "
            "continuous function on a compact domain."
        ),
    },
    {
        "domain": "betterexplained.com",
        "year_range": (2013, 2021),
        "content_type": "blog",
        "url_slug": "an-intuitive-guide-to-fourier-transform",
        "text": (
            "The Fourier Transform is one of the most useful mathematical tools, but "
            "textbook explanations often bury the intuition in formulas. Here's the "
            "core idea: any signal (sound, image, data over time) can be decomposed "
            "into a sum of pure sinusoids at different frequencies.\n\n"
            "Think of it as a recipe. Given the final cake (your signal), the Fourier "
            "transform finds the recipe — what frequencies (ingredients) at what "
            "amplitudes (amounts) combine to produce it. The inverse Fourier transform "
            "bakes the cake from the recipe.\n\n"
            "Why does this matter? Because many operations are easier in frequency space "
            "than in time space. Audio equalization: multiply the frequency components "
            "you want to amplify, attenuate the ones you want to reduce, inverse transform. "
            "Image compression (JPEG): discard high-frequency components the eye can't "
            "see well, store the rest. Convolution in time domain is multiplication in "
            "frequency domain — this makes filtering dramatically faster."
        ),
    },
    # ── MEDICINE / HEALTH ─────────────────────────────────────────────────────
    {
        "domain": "medicalnewstoday.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "antibiotic-resistance-explained",
        "text": (
            "Antibiotic resistance is one of the most pressing threats to global health. "
            "The mechanism is evolution: antibiotics kill susceptible bacteria, but "
            "any bacteria with mutations conferring resistance survive and reproduce. "
            "The more antibiotics are used, the stronger this selection pressure.\n\n"
            "Agricultural use drives significant resistance. Roughly 80% of antibiotic "
            "use in the United States is in agriculture — often administered at "
            "sub-therapeutic doses to promote growth, which is ideal for selecting "
            "resistance without killing the host bacteria. These resistant bacteria "
            "can spread to humans through food, water, or contact.\n\n"
            "The pipeline of new antibiotics is nearly empty. Antibiotics are taken for "
            "one to two weeks and cure the patient — an unfavorable business model "
            "compared to drugs for chronic conditions. Basic research into novel "
            "antibiotic targets has atrophied. The world faces a future where "
            "routine infections become potentially fatal again."
        ),
    },
    {
        "domain": "nejm.org",
        "year_range": (2017, 2021),
        "content_type": "article",
        "url_slug": "randomized-controlled-trials-gold-standard",
        "text": (
            "The randomized controlled trial is the bedrock of evidence-based medicine. "
            "By randomly assigning patients to treatment and control groups, RCTs eliminate "
            "selection bias — the tendency for sicker or healthier patients to choose "
            "different treatments. Random assignment creates groups that, on average, "
            "differ only in the treatment received.\n\n"
            "Blinding removes placebo effects and observer bias. In a double-blind trial, "
            "neither patients nor the clinicians assessing outcomes know who received the "
            "treatment. This prevents both the placebo response (real biological changes "
            "triggered by the expectation of improvement) and unconscious bias in how "
            "clinicians evaluate and record outcomes.\n\n"
            "The limitation: RCTs answer 'does this treatment work in this population "
            "under these conditions?' Generalizability is always uncertain. Trial "
            "populations often exclude elderly patients, those with comorbidities, "
            "and pregnant women — exactly the populations most likely to need treatment. "
            "External validity requires careful consideration beyond the p-value."
        ),
    },
]

# ── Additional diverse domain templates ─────────────────────────────────────────

EXTRA_CONTENT = [
    {
        "domain": "arstechnica.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "history-of-video-game-consoles",
        "text": (
            "The history of home game consoles traces from Magnavox Odyssey (1972) through "
            "the industry crash of 1983 — when a flooded market of poor games nearly killed "
            "home gaming — to Nintendo's miraculous recovery with the NES in 1985. The NES "
            "succeeded through strict quality control: Nintendo's seal of approval meant "
            "third parties had to meet minimum standards, and they limited the number of "
            "cartridges publishers could release annually.\n\n"
            "The 16-bit wars between Sega Genesis and Super Nintendo (1990-1994) defined "
            "gaming's adolescence. Sega's aggressive marketing ('Genesis does what Nintendon't') "
            "gave them 55% market share at peak. Then Sony entered with PlayStation (1994), "
            "shifting gaming to CD-ROM and 3D graphics. Sega's response — Saturn — was "
            "expensive and hard to develop for. Sega exited hardware in 2001.\n\n"
            "The 2000s brought Xbox and the beginning of online console gaming. Halo defined "
            "console shooters; Xbox Live created the social layer. The Wii's motion controls "
            "expanded gaming to demographics that had never played. The current era of "
            "PlayStation 5 and Xbox Series X represents incremental evolution rather "
            "than paradigm shifts — the revolution is in mobile gaming and live services."
        ),
    },
    {
        "domain": "theguardian.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "social-media-mental-health-teenagers",
        "text": (
            "The rise in adolescent mental health problems in the United States and United "
            "Kingdom is striking: depression and anxiety rates among teenagers climbed "
            "sharply around 2012, particularly among girls. Jean Twenge and Jonathan Haidt "
            "argue this correlates with smartphone adoption and the rise of Instagram.\n\n"
            "The mechanisms they propose: social media enables constant social comparison, "
            "and curated feeds present idealized images. Nighttime phone use disrupts sleep, "
            "which directly worsens mental health. Cyberbullying extends bullying beyond "
            "school hours. Girls are more affected than boys, possibly because their social "
            "hierarchies rely more on appearance and social status.\n\n"
            "The evidence is contested. Correlational data can't establish causation; "
            "many other factors changed simultaneously. Amy Orben's research suggests "
            "screen time's effect size is smaller than commonly claimed — comparable to "
            "wearing glasses or eating potatoes. The policy implications of these "
            "disagreements are significant: restricting teen social media access could "
            "harm more than help if the causal story is wrong."
        ),
    },
    {
        "domain": "financialsamurai.com",
        "year_range": (2013, 2021),
        "content_type": "blog",
        "url_slug": "what-i-learned-leaving-banking",
        "text": (
            "I left investment banking at 34 with enough saved to be financially independent. "
            "People always ask: was it worth it? And I never know exactly how to answer "
            "that, because the 13 years I spent getting there cost something real.\n\n"
            "What surprised me about early retirement: the identity questions hit harder "
            "than I expected. In banking, you are your job. You have a clear hierarchy, "
            "measurable performance, and social status that comes with the title. When "
            "you leave, you have to figure out who you are without any of that scaffolding.\n\n"
            "The money question is simpler than people think: you need roughly 25 times "
            "your annual expenses (the 4% rule — you can withdraw 4% annually and the "
            "portfolio should last 30+ years in most historical scenarios). The hard part "
            "isn't the math. It's the psychological work of decoupling your self-worth "
            "from your net worth, and finding meaning in a structure you build yourself "
            "rather than one handed to you."
        ),
    },
    {
        "domain": "cnn.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "electric-vehicles-2021-state",
        "text": (
            "Electric vehicles crossed several meaningful thresholds in 2021. Global EV "
            "sales exceeded 6 million, a 100% year-over-year increase. Norway became the "
            "first country where EVs outsold combustion vehicles — over 60% market share. "
            "Tesla remained the dominant pure-EV manufacturer, but Volkswagen, Ford, and "
            "General Motors began delivering on long-promised EV transitions.\n\n"
            "Range anxiety has become less justifiable. The 2021 Tesla Model 3 Long Range "
            "achieves 358 miles EPA-rated. The Ford Mustang Mach-E does 305 miles. "
            "More importantly, charging infrastructure is growing rapidly: Tesla's "
            "Supercharger network has over 25,000 connectors globally; Electrify America "
            "and ChargePoint are expanding rapidly.\n\n"
            "The transition creates winners and losers. Battery gigafactories are being "
            "built across the US, Europe, and China. But combustion engine suppliers, "
            "gas stations, and oil refiners face structural decline. The pace of "
            "transition depends critically on battery costs — below $100/kWh, EVs "
            "become cheaper than combustion at purchase price, not just lifetime cost."
        ),
    },
    {
        "domain": "vox.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "how-zoning-caused-housing-crisis",
        "text": (
            "The American housing crisis is substantially self-inflicted. Cities where "
            "people most want to live — San Francisco, New York, Boston, Seattle — have "
            "used zoning law to restrict housing construction for decades. Single-family "
            "zoning covers roughly 75% of San Francisco's residential land, making it "
            "illegal to build apartments on three-quarters of the city.\n\n"
            "The consequences are predictable: when demand grows and supply can't, prices "
            "rise. San Francisco's median home price is over $1.4 million. Teachers, "
            "nurses, firefighters, and service workers are priced out of the cities "
            "they serve. Long commutes replace proximity. Economic opportunity concentrates "
            "in expensive places while workers are excluded.\n\n"
            "The political economy of exclusionary zoning: homeowners benefit from high "
            "property values and have strong incentives to show up to zoning meetings. "
            "Potential future residents who would benefit from housing construction aren't "
            "yet there to vote. The YIMBY movement ('Yes In My Backyard') has organized "
            "in response, achieving upzoning victories in California and Oregon."
        ),
    },
    {
        "domain": "wired.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "deepfakes-synthetic-media",
        "text": (
            "Deepfakes emerged in 2017 when a Reddit user posted face-swapped celebrity "
            "videos. The underlying technique — using generative adversarial networks to "
            "synthesize realistic video of real people — had been developed in academic "
            "settings. What changed was that it became accessible enough for non-experts "
            "to use with commodity hardware.\n\n"
            "The technology has legitimate uses: de-aging actors in films, historical "
            "education, entertainment. The harms are more obvious: non-consensual "
            "intimate imagery (92% of deepfake videos online are non-consensual pornography, "
            "almost exclusively targeting women), political manipulation, financial fraud.\n\n"
            "Detection tools exist but remain in an arms race with generation quality. "
            "The FBI warned in 2021 that malicious actors are using deepfake video and "
            "audio for spear phishing attacks — impersonating executives in video calls "
            "to authorize wire transfers. The harder problem is epistemological: once "
            "people know video can be faked, authentic video loses evidential weight."
        ),
    },
    {
        "domain": "engineering.atspotify.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "spotify-recommendation-system",
        "text": (
            "Spotify's recommendation system has to solve a genuinely hard problem: "
            "60 million tracks, 400 million users, highly personal and contextual "
            "preferences. Discover Weekly sends personalized playlists to 100 million "
            "users every Monday and has become one of Spotify's most loved features.\n\n"
            "The core technique is collaborative filtering: users with similar listening "
            "histories to yours tend to enjoy similar music. Matrix factorization decomposes "
            "the user-track listening matrix into latent factors representing something like "
            "'tastes' and 'characteristics.' Users and tracks are embedded in the same "
            "space; proximity predicts affinity.\n\n"
            "Collaborative filtering alone fails for new tracks (cold start problem) and "
            "niche music. Spotify augments it with audio features (spectral analysis, "
            "tempo, key, mood), natural language processing on lyrics and editorial "
            "descriptions, and graph-based approaches modeling the network of artists, "
            "playlists, and listeners. The system runs hundreds of A/B experiments "
            "simultaneously to continuously improve recommendation quality."
        ),
    },
    {
        "domain": "bloomberg.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "how-supply-chains-broke-in-2021",
        "text": (
            "The supply chain crises of 2021 revealed how complex and fragile global "
            "production networks had become. When the Ever Given container ship blocked "
            "the Suez Canal for six days in March 2021, an estimated $9.6 billion in "
            "cargo was stuck per day. The canal carries roughly 12% of global trade.\n\n"
            "The deeper problem predated the blockage. COVID-19 disrupted manufacturing "
            "in waves: factories shuttered, workers couldn't come to work, demand "
            "patterns shifted unexpectedly. Semiconductor shortages idled automobile "
            "factories — a car contains 1,000-3,000 chips, and a shortage of $1 chips "
            "could halt production of a $40,000 vehicle.\n\n"
            "Just-in-time manufacturing, which minimized inventory costs over decades, "
            "proved to have hidden fragility: it assumed supply chains would function "
            "smoothly and shock-resistant inventory buffers were unnecessary waste. "
            "Companies are now reassessing. 'Just-in-case' inventory buffers are "
            "expensive but may be worth paying for resilience."
        ),
    },
    {
        "domain": "theconversation.com",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "why-experts-disagree-about-diet",
        "text": (
            "Nutrition science produces contradictory findings with remarkable consistency. "
            "Butter was bad, then good. Eggs were bad, then fine. Fat was the enemy in "
            "the 1980s; in the 2010s, carbs became the villain. Why is nutrition "
            "so difficult to study?\n\n"
            "The core problem is confounding. Randomized controlled trials are the "
            "gold standard for establishing causation, but you can't blind someone to "
            "what they eat, and dietary trials lasting years are enormously expensive. "
            "Observational studies ask people to remember what they ate and correlate "
            "it with health outcomes — but people are bad at remembering food intake, "
            "and diet correlates with hundreds of other lifestyle factors.\n\n"
            "Publication bias worsens everything: surprising findings (coffee prevents "
            "cancer!) get published; null results don't. Industry funding shapes "
            "research questions and interpretation. Biological heterogeneity means "
            "the same diet affects different people differently. The honest answer is "
            "that we know much less about optimal human nutrition than the confident "
            "headlines suggest."
        ),
    },
    {
        "domain": "stratechery.com",
        "year_range": (2014, 2021),
        "content_type": "blog",
        "url_slug": "aggregation-theory",
        "text": (
            "The fundamental insight of Aggregation Theory: the internet has made "
            "distribution free. Before the internet, the companies that controlled "
            "distribution — publishers, record labels, TV networks, retailers — had "
            "enormous leverage over suppliers (authors, musicians, content creators, "
            "manufacturers). Scarcity of shelf space and broadcast spectrum made "
            "distributors essential.\n\n"
            "The internet changed this. Google, Facebook, Amazon, and Netflix control "
            "demand, not supply. They aggregate users with zero marginal cost of adding "
            "more users, and then compete for suppliers (websites, news, products, content) "
            "on the strength of that user base. Suppliers must come to the aggregator "
            "or lose access to the market.\n\n"
            "This is why regulatory frameworks built around supply-side control — "
            "antitrust law designed for industrial-era monopolies — struggle with "
            "internet aggregators. Google doesn't own the information it indexes; "
            "Facebook doesn't own the social graph it monetizes. The leverage is "
            "entirely on the demand side, through user relationships."
        ),
    },
]


DIVERSE_TEMPLATES = [
    # ── FOOD / RECIPES ────────────────────────────────────────────────────────
    {
        "domain": "allrecipes.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "homemade-blueberry-jam-no-pectin",
        "text": (
            "Making blueberry jam at home is simpler than most people think, and the result "
            "beats anything you can buy at the store. The key is using the fruit's natural "
            "pectin, which concentrates as you cook. Fresh or frozen blueberries both work "
            "beautifully — frozen often have better flavor in winter since they're picked ripe.\n\n"
            "Start with four cups of blueberries and two cups of sugar. Mash half the berries "
            "with a potato masher — leave the rest whole for texture. Add the sugar and two "
            "tablespoons of lemon juice. The lemon does two things: it activates pectin and "
            "brightens the flavor, cutting through the sweetness.\n\n"
            "Cook over medium-high heat, stirring frequently. Skim any foam that rises. "
            "After 20-25 minutes, the jam is done when it passes the wrinkle test: spoon "
            "a small amount onto a chilled plate, let it sit 30 seconds, then push with "
            "your finger. If it wrinkles and holds its shape, it's set. Pour into sterilized "
            "jars while hot. This recipe yields about three half-pint jars."
        ),
    },
    {
        "domain": "seriouseats.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "sourdough-bread-beginners-guide",
        "text": (
            "Sourdough is a commitment. You're cultivating a living culture — wild yeast and "
            "lactic acid bacteria that you keep alive indefinitely and use to leaven bread. "
            "The flavor complexity you get from a long, cold fermentation is something "
            "commercial yeast simply cannot replicate.\n\n"
            "The starter: mix equal weights of flour and water in a jar. Leave at room "
            "temperature. Every day, discard half and feed fresh flour and water. After "
            "five to seven days, your starter will be reliably doubling in size within "
            "four hours of feeding — that's when it's ready to bake with.\n\n"
            "For the bread: autolyse your flour and water for 30 minutes before adding "
            "starter and salt. This develops gluten passively. Do four sets of stretch-and-fold "
            "during the three-hour bulk fermentation, then shape, place in a floured banneton, "
            "and cold-proof overnight. Bake in a Dutch oven at 500°F — the steam trapped "
            "inside creates the open crumb and glossy crust sourdough is known for."
        ),
    },
    {
        "domain": "thekitchn.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "perfect-scrambled-eggs-gordon-ramsay-method",
        "text": (
            "Most people overcook scrambled eggs. High heat and constant stirring give you "
            "rubbery, dry curds that bounce off the pan. The secret is low heat, patience, "
            "and taking them off before they look done.\n\n"
            "Gordon Ramsay's method: crack eggs directly into a cold pan. Add butter. Turn "
            "heat to medium-low. Stir continuously with a spatula, scraping the bottom and "
            "sides. Crucially, take the pan off the heat every 30 seconds and continue "
            "stirring — the residual heat is enough to cook. Add a dollop of crème fraîche "
            "or cream cheese in the last 30 seconds. Season with salt only at the end.\n\n"
            "The result is loose, creamy, glossy curds — almost like a custard — rather "
            "than the dry chunks most people are used to. The whole process takes four "
            "to five minutes. It feels slow but eggs cooked this way are dramatically better."
        ),
    },
    {
        "domain": "food52.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "how-to-make-perfect-bbq-ribs",
        "text": (
            "Competition barbecue is built on the 3-2-1 method for pork ribs: three hours "
            "uncovered in smoke, two hours wrapped in foil with liquid, one hour unwrapped "
            "to firm up the bark. It produces fall-off-the-bone ribs that win the crowd "
            "every time, though purists argue that real barbecue ribs should have more "
            "resistance — the meat should pull clean from the bone, not fall.\n\n"
            "The rub matters more than the sauce. Kosher salt, black pepper, smoked paprika, "
            "garlic powder, a touch of cayenne and brown sugar — apply generously the night "
            "before and let it penetrate. Remove the silverskin membrane from the back "
            "of the rack or it becomes a chewy barrier that blocks smoke and seasoning.\n\n"
            "Temperature control is everything in barbecue. Maintain 225-250°F. Any hotter "
            "and you're roasting, not smoking. Any cooler and you'll be there all day. "
            "Use a reliable wood: hickory for strong flavor, apple or cherry for mild. "
            "Too much smoke makes ribs bitter — a thin blue smoke is ideal, not billowing white."
        ),
    },
    {
        "domain": "cookinglight.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "mediterranean-diet-week-meal-plan",
        "text": (
            "The Mediterranean diet consistently ranks as one of the healthiest eating "
            "patterns in the world. Unlike most diets, it's not about restriction — it's "
            "about abundance: vegetables, legumes, whole grains, fish, olive oil, and "
            "moderate wine. Red meat appears occasionally. Processed food rarely.\n\n"
            "Monday: Greek salad with chickpeas, feta, kalamata olives, cucumber, tomato, "
            "dressed with olive oil and oregano. Whole grain pita on the side. Tuesday: "
            "baked salmon with lemon, capers, and herbs over brown rice with roasted "
            "vegetables. Wednesday: lentil soup with crusty bread and a simple salad.\n\n"
            "The research base is strong. The PREDIMED trial randomized over 7,000 people "
            "to a Mediterranean diet or low-fat diet and found 30% reduction in cardiovascular "
            "events in the Mediterranean group. Observational studies consistently show "
            "lower rates of depression, cognitive decline, and several cancers in "
            "Mediterranean diet adherents."
        ),
    },
    # ── SPORTS / FITNESS ──────────────────────────────────────────────────────
    {
        "domain": "runnersworld.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "marathon-training-plan-beginner",
        "text": (
            "Training for your first marathon is a four to five month commitment. The "
            "biggest mistake beginners make is doing long runs too fast. Your long run "
            "pace should be 60-90 seconds per mile slower than your goal race pace — "
            "it should feel conversational, almost embarrassingly slow. The goal is time "
            "on feet and aerobic adaptation, not speed.\n\n"
            "The 16-week plan builds mileage gradually — no more than 10% increase per "
            "week to avoid injury. Week 1 peaks at 25 miles. Week 12 peaks at 45 miles. "
            "Your longest run is 20-22 miles, done three weeks before race day. After "
            "that: three weeks of tapering, reducing mileage to let your body recover "
            "and consolidate adaptations.\n\n"
            "Nutrition matters more as runs get longer. Practice your race nutrition on "
            "long runs — don't try anything new on race day. For runs over 90 minutes, "
            "take in 30-60g of carbohydrate per hour via gels, chews, or sports drink. "
            "Dehydration impairs performance; over-hydration is dangerous. Drink to thirst."
        ),
    },
    {
        "domain": "si.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "greatest-nba-dynasties-of-all-time",
        "text": (
            "Debates about the greatest NBA dynasty always circle back to two franchises: "
            "the Boston Celtics of the Bill Russell era and the Chicago Bulls of Michael "
            "Jordan. The Celtics won eight consecutive championships from 1959 to 1966 — "
            "a record that will almost certainly never be broken. Russell was the engine: "
            "his defensive presence, rebounding, and winning culture made the Celtics "
            "virtually unbeatable in the playoffs.\n\n"
            "Jordan's Bulls won six titles in eight years, never losing a Finals. The "
            "triangle offense, Phil Jackson's Zen coaching, Scottie Pippen's underrated "
            "brilliance, and Jordan's competitive fury created something unprecedented. "
            "Jordan went 6-0 in Finals appearances, was Finals MVP all six times.\n\n"
            "The modern argument is the Golden State Warriors: five Finals appearances "
            "in five years, three championships, the greatest offensive juorum system ever "
            "assembled around Curry's shooting. Context always complicates these comparisons — "
            "different eras, different rules, different competition."
        ),
    },
    {
        "domain": "bicycling.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "cycling-training-zones-explained",
        "text": (
            "Training zones are the framework professional cyclists use to structure "
            "every ride with purpose. Rather than riding at random effort, you target "
            "specific physiological adaptations by staying within defined intensity bands.\n\n"
            "Zone 1 is active recovery — barely above resting heart rate, used the day "
            "after a hard effort. Zone 2 is the aerobic base — a pace you can hold for "
            "hours, where you're burning mostly fat and building mitochondrial density. "
            "Most of your training volume should be here. Zone 3 is 'junk miles' to many "
            "coaches — hard enough to accumulate fatigue but not hard enough to drive "
            "significant adaptation.\n\n"
            "Zone 4 is threshold — the intensity you can sustain for about an hour, where "
            "lactate production equals clearance. Training here improves your sustainable "
            "power. Zone 5 is VO2max work — hard intervals lasting 3-8 minutes that "
            "raise your aerobic ceiling. This is where fitness gains accelerate but "
            "injury and burnout risk also rise."
        ),
    },
    {
        "domain": "stack.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "strength-training-fundamentals-beginners",
        "text": (
            "Strength training is one of the most evidence-backed interventions for "
            "health and longevity. Building muscle increases resting metabolic rate, "
            "improves insulin sensitivity, strengthens bones, and reduces injury risk "
            "in other activities. You don't need a gym — bodyweight training can produce "
            "significant adaptations, especially for beginners.\n\n"
            "The principle of progressive overload is fundamental: you must continually "
            "increase the challenge to drive adaptation. For beginners, adding weight "
            "every session is realistic. For intermediate lifters, weekly progression "
            "is the target. The key is tracking — if you're not measuring, you can't "
            "know if you're progressing.\n\n"
            "Start with compound movements: squat, deadlift, bench press, overhead press, "
            "row. These recruit the most muscle mass and drive the most systemic adaptation. "
            "Add isolation work — curls, lateral raises, tricep work — only after the "
            "compounds are solid. Three days per week of full-body training is optimal "
            "for most beginners. Rest is when the adaptation happens."
        ),
    },
    # ── MUSIC ─────────────────────────────────────────────────────────────────
    {
        "domain": "pitchfork.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "essential-jazz-albums-beginners-guide",
        "text": (
            "Jazz has an intimidating reputation, but its greatest albums are as immediate "
            "and emotional as any pop record. Start with Miles Davis's Kind of Blue (1959) — "
            "the best-selling jazz album ever, built on modal improvisation that still sounds "
            "modern. Davis assembled the greatest jazz ensemble ever: Coltrane, Bill Evans, "
            "Cannonball Adderley, Paul Chambers, Jimmy Cobb.\n\n"
            "From there: John Coltrane's A Love Supreme (1964) — a four-part suite that "
            "functions as a spiritual meditation, each movement building intensity until "
            "the final 'Psalm' where Coltrane plays the words of his written poem. "
            "Charles Mingus's Mingus Ah Um (1959) is a revelation — blues, gospel, bop, "
            "and orchestral ambition coexisting in one record.\n\n"
            "For something more modern: Bill Evans's Waltz for Debby (1961), recorded live "
            "at the Village Vanguard, captures the intimacy of jazz in a small club. "
            "Ornette Coleman's The Shape of Jazz to Come anticipated free jazz. "
            "Herbie Hancock's Head Hunters (1973) fused jazz with funk and opened "
            "a new commercial era."
        ),
    },
    {
        "domain": "rollingstone.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "history-of-hip-hop-from-bronx-to-global",
        "text": (
            "Hip-hop was invented in the Bronx in the summer of 1973. DJ Kool Herc's "
            "back-to-school party on Sedgwick Avenue is the traditional origin point — "
            "Herc played the percussion breaks of funk and soul records on two turntables, "
            "extending the breakbeat for dancers. From this basic innovation came scratching, "
            "sampling, MCing, and eventually an entire culture.\n\n"
            "Grandmaster Flash refined Herc's technique. Afrika Bambaataa brought "
            "electronic music via Kraftwerk into the mix with 'Planet Rock.' Sugar Hill "
            "Gang took it to radio. Run-DMC brought rock crossover. N.W.A made it raw "
            "and confrontational. Rakim elevated the lyrical complexity. By 1990, "
            "hip-hop was America's most vital musical form.\n\n"
            "The 90s golden age: Biggie, Tupac, Nas, Jay-Z, Wu-Tang Clan, OutKast. "
            "Each artist defined a regional sound while advancing the art form. "
            "By 2019, hip-hop was the most consumed music genre globally, "
            "with streaming numbers that dwarfed rock, pop, and country."
        ),
    },
    {
        "domain": "guitarworld.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "fingerstyle-guitar-techniques-beginners",
        "text": (
            "Fingerstyle guitar — using the fingers instead of a pick — opens up "
            "a completely different sonic palette. You can play melody, bass, and "
            "harmony simultaneously, creating the impression of multiple instruments. "
            "Classical guitarists, folk players, and fingerpickers like Chet Atkins, "
            "Tommy Emmanuel, and Merle Travis built careers on this technique.\n\n"
            "Start with Travis picking: your thumb alternates between the bass strings "
            "(strings 4, 5, 6) while your fingers pick melody on the treble strings. "
            "The pattern is constant — thumb on beats one and three, fingers filling "
            "between. Once you internalize the thumb independence, melodies can float "
            "above the steady bass almost automatically.\n\n"
            "Nail length and angle matter. Many fingerstyle players grow their right-hand "
            "nails slightly — the nail-tip combination produces a brighter tone than "
            "flesh alone. Angle your finger contact across the string for a warmer "
            "tone; increase the nail ratio for brightness. Classical technique uses "
            "the free stroke (apoyando) and rest stroke (tirando) — both worth learning."
        ),
    },
    # ── FILM / TV ─────────────────────────────────────────────────────────────
    {
        "domain": "rogerebert.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "2001-a-space-odyssey-kubrick-analysis",
        "text": (
            "Stanley Kubrick's 2001: A Space Odyssey (1968) is the most rigorous science "
            "fiction film ever made. Kubrick and Arthur C. Clarke deliberately avoided "
            "exposition — there's almost no dialogue in the first 25 minutes, and the "
            "final 25 minutes have almost none. The film communicates visually, through "
            "music, and through the accumulated weight of what you've seen.\n\n"
            "The film is structured as three movements separated by temporal leaps of "
            "millions of years. The match cut from bone to spacecraft is perhaps cinema's "
            "most famous edit: a blunt statement about the continuity of human violence "
            "and technological evolution. Johann Strauss's Blue Danube plays over the "
            "station docking sequence — Kubrick's way of saying spaceflight would become "
            "as ordinary as a waltz.\n\n"
            "HAL 9000 remains one of cinema's great villains, but he's also its most "
            "sympathetic — a creation turned against its creators because of an impossible "
            "contradiction in its programming. The ending resists explanation by design. "
            "Kubrick said he didn't want audiences to think, he wanted them to feel. "
            "Half a century later, viewers still feel it."
        ),
    },
    {
        "domain": "avclub.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "best-tv-dramas-of-the-2010s",
        "text": (
            "Television drama reached an artistic peak in the 2010s that rivals the best "
            "cinema. The form's advantages — length for character development, season-long "
            "arcs, the ability to sustain slow burns — aligned perfectly with the stories "
            "the decade demanded.\n\n"
            "Breaking Bad completed its run and consolidated its place as perhaps the most "
            "perfectly plotted drama ever made. The Wire, from the decade before, continued "
            "to grow in reputation — a five-season portrait of American institutional failure "
            "that plays like a novel. Mad Men gave us Don Draper, one of the most richly "
            "ambiguous protagonists in TV history.\n\n"
            "Game of Thrones (seasons 1-4) showed that fantasy could sustain serious drama. "
            "Succession arrived in 2018 and immediately felt essential — Shakespearean "
            "dynamics in a Murdoch-analog media empire, performed by a cast that found "
            "the comedy and tragedy in every scene. Atlanta, Fleabag, and The Americans "
            "each expanded what television could do. The 2010s will be remembered as "
            "the decade TV finally grew up."
        ),
    },
    # ── HEALTH / WELLNESS ─────────────────────────────────────────────────────
    {
        "domain": "healthline.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "anxiety-management-evidence-based-techniques",
        "text": (
            "Anxiety disorders are the most common mental health condition in the United "
            "States, affecting 40 million adults. The good news: anxiety responds well "
            "to treatment, particularly cognitive-behavioral therapy (CBT) and specific "
            "lifestyle interventions backed by good evidence.\n\n"
            "The physiological basis of anxiety is the fight-or-flight response. Your "
            "sympathetic nervous system activates: heart rate and breathing increase, "
            "muscles tense, digestion slows. This response evolved for real threats. "
            "With anxiety disorders, it activates inappropriately — in response to "
            "perceived social threats, abstract worries, or nothing identifiable at all.\n\n"
            "Evidence-based techniques: diaphragmatic breathing activates the "
            "parasympathetic nervous system within minutes — breathe in for 4 counts, "
            "hold for 4, out for 6. Progressive muscle relaxation systematically "
            "tenses and releases muscle groups. Exercise is remarkably effective — "
            "aerobic activity produces immediate anxiolytic effects and, practiced "
            "regularly, reduces baseline anxiety. Cognitive restructuring challenges "
            "catastrophic thinking by examining evidence for and against anxious beliefs."
        ),
    },
    {
        "domain": "sleepfoundation.org",
        "year_range": (2016, 2021),
        "content_type": "article",
        "url_slug": "sleep-hygiene-how-to-fix-your-sleep",
        "text": (
            "Chronic sleep deprivation is a public health crisis. The CDC estimates "
            "that one in three Americans doesn't get enough sleep. The consequences "
            "accumulate: impaired cognition, weakened immunity, increased cardiovascular "
            "risk, weight gain, mood disorders. Matthew Walker's research suggests that "
            "insufficient sleep may be the greatest public health challenge of our time.\n\n"
            "Sleep hygiene is the collection of habits that support good sleep. The most "
            "important: maintain a consistent sleep schedule seven days a week — your "
            "circadian rhythm is a clock that doesn't understand weekends. Going to bed "
            "and waking up at the same time is more important than the total hours.\n\n"
            "Temperature matters more than most people realize. Your core body temperature "
            "needs to drop 1-2°F to initiate sleep. Keep your bedroom cool — 65-68°F "
            "is optimal for most people. Light is the primary circadian cue: bright "
            "light in the morning advances your clock; blue light at night delays it. "
            "Dim lights and avoid screens in the hour before bed."
        ),
    },
    {
        "domain": "webmd.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "high-blood-pressure-lifestyle-changes",
        "text": (
            "High blood pressure (hypertension) affects nearly half of American adults "
            "and is a leading risk factor for heart attack, stroke, and kidney disease. "
            "The insidious thing about hypertension is that it has no symptoms — "
            "you can have dangerously high readings for years without knowing it.\n\n"
            "Lifestyle interventions can reduce blood pressure substantially, sometimes "
            "eliminating the need for medication. The DASH diet (Dietary Approaches to "
            "Stop Hypertension) reduces systolic blood pressure by 8-14 mmHg — comparable "
            "to a medication. DASH emphasizes vegetables, fruits, whole grains, lean "
            "protein, and drastically reduced sodium.\n\n"
            "Regular aerobic exercise lowers blood pressure by 5-8 mmHg. Losing just "
            "10 pounds reduces systolic pressure by 5-10 mmHg. Reducing sodium intake "
            "below 2,300mg per day (the current American average is over 3,400mg) "
            "has significant effects. Limiting alcohol and quitting smoking further "
            "reduce risk. These interventions combine multiplicatively."
        ),
    },
    # ── TRAVEL ────────────────────────────────────────────────────────────────
    {
        "domain": "lonelyplanet.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "japan-two-week-itinerary",
        "text": (
            "Japan rewards the traveler who slows down. Two weeks gives you time to "
            "move beyond the obvious and find the texture that makes Japan unlike "
            "anywhere else on earth.\n\n"
            "Days 1-3, Tokyo: Start in Shinjuku to get your bearings in the organized "
            "chaos. Spend a morning in Yanaka — a neighborhood that survived WWII bombing "
            "and the 1923 earthquake, still feeling like old Tokyo with its wooden "
            "temples and local shotengai shopping street. The Tokyo National Museum "
            "in Ueno houses the world's largest collection of Japanese art.\n\n"
            "Days 4-5, Nikko: Day trip or overnight. The Toshogu shrine complex is "
            "baroque Edo-period excess — every surface carved and gilded. The forest "
            "around it is centuries-old cedar.\n\n"
            "Days 6-8, Kyoto: Move slowly. Fushimi Inari at 5am before the crowds. "
            "Nishiki Market for street food. The bamboo grove in Arashiyama at golden "
            "hour. Kinkaku-ji is overcrowded but genuinely dazzling. A multi-course "
            "kaiseki dinner somewhere mid-range — not the most expensive, just "
            "the most careful."
        ),
    },
    {
        "domain": "travelandleisure.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "camino-de-santiago-complete-guide",
        "text": (
            "The Camino de Santiago is a network of pilgrimage routes across Europe "
            "converging on the Cathedral of Santiago de Compostela in Galicia, Spain, "
            "where the remains of Saint James the Apostle are said to rest. People "
            "have walked it for a thousand years; around 300,000 do it annually today, "
            "the large majority non-religious, drawn by something harder to name.\n\n"
            "The most popular route is the Camino Francés — the French Way — beginning "
            "in Saint-Jean-Pied-de-Port in France and running 780 kilometers over "
            "30-35 days. The first stage, over the Pyrenees to Roncesvalles, is the "
            "most physically demanding. After that, the Meseta — the flat central plateau — "
            "is where many pilgrims report hitting their stride, or their wall.\n\n"
            "Pack light. Lighter than you think. The standard pilgrimage kit: 8-10kg "
            "including pack, sleeping bag liner, three sets of clothing, first aid, "
            "waterproofs. Blisters are nearly universal; treat them early. Albergues "
            "(pilgrim hostels) cost 10-15 euros and provide bunks, showers, sometimes "
            "a communal dinner. The community that forms on the Camino is one of "
            "its main attractions."
        ),
    },
    # ── PARENTING ─────────────────────────────────────────────────────────────
    {
        "domain": "parents.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "sleep-training-methods-explained",
        "text": (
            "Sleep training is one of the most contentious topics in parenting, which "
            "is remarkable given how strong the evidence is. The science consistently "
            "shows that graduated extinction methods (the 'cry it out' approach) and "
            "gentler graduated approaches both work — babies learn to self-soothe, "
            "sleep improves for the whole family, and there's no evidence of long-term "
            "emotional harm.\n\n"
            "The Ferber method: put baby down drowsy but awake, leave, return at "
            "progressively longer intervals (3 min, 5 min, 10 min) to reassure without "
            "picking up. The no-cry alternatives use gradual withdrawal — the chair "
            "method, for example, sits a parent progressively farther from the crib "
            "each night until they're out of the room.\n\n"
            "The prerequisite most sleep training guides skip: developmental readiness. "
            "Most babies are physiologically ready to sleep through the night by "
            "4-6 months, when they can consolidate sleep cycles without feeding. "
            "Before that, night waking is biologically normal and expected. "
            "Starting too early is the most common mistake."
        ),
    },
    {
        "domain": "babycenter.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "teaching-kids-about-money-by-age",
        "text": (
            "Financial literacy starts earlier than most parents realize. Children as "
            "young as three can grasp basic concepts of spending and saving. By seven, "
            "research suggests, many of the core money habits that persist into adulthood "
            "are already formed.\n\n"
            "Ages 3-5: introduce the idea that things cost money and money is earned. "
            "A clear piggy bank lets them see savings accumulate. Small chores for small "
            "allowance establishes the work-reward connection. Let them make small "
            "purchase decisions — this week's treat, which toy at the store — and "
            "experience the tradeoff.\n\n"
            "Ages 8-12: introduce saving goals. A visible chart tracking progress "
            "toward a desired item teaches delayed gratification better than any "
            "lecture. Introduce the three-jar system: spending, saving, giving. "
            "The giving jar teaches that money can be used for others, not just self.\n\n"
            "Teenagers: bank accounts, debit cards, and the concept of interest. "
            "Let them experience small financial mistakes now — an overdrafted account, "
            "an impulse purchase regretted — when the stakes are still low."
        ),
    },
    # ── GAMING ────────────────────────────────────────────────────────────────
    {
        "domain": "polygon.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "greatest-rpgs-of-all-time-ranked",
        "text": (
            "Role-playing games are the form where video games most clearly function as "
            "literature. The greatest RPGs are world-building exercises that rival "
            "any novel for depth of character and complexity of moral choice.\n\n"
            "Planescape: Torment (1999) is the most written-about game in critical circles "
            "for good reason — its central question ('What can change the nature of a man?') "
            "drives a meditation on identity, mortality, and redemption that no other game "
            "has approached. The writing makes most fantasy fiction look shallow.\n\n"
            "The Witcher 3 (2015) represents the open-world RPG at its peak. Geralt of Rivia "
            "is one of gaming's few adult protagonists — a man of genuine moral ambiguity "
            "navigating a world where choices have weight. The expansions, Blood and Wine "
            "and Hearts of Stone, are better than most full games.\n\n"
            "Dark Souls reframed difficulty as communication. The environment tells the "
            "story. Death teaches the mechanics. The community built its lore collaboratively. "
            "FromSoftware created a genre — the Soulslike — that has proven endlessly "
            "generative for other developers."
        ),
    },
    {
        "domain": "kotaku.com",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "minecraft-why-it-endures",
        "text": (
            "Minecraft was released in beta in 2009 and became the best-selling video game "
            "of all time by 2019, with over 238 million copies sold. It achieved this "
            "without a story, without combat that would satisfy any action gamer, without "
            "graphics that have impressed anyone since 2011. It succeeded entirely on the "
            "strength of one idea: give players infinite building materials and let them "
            "make whatever they imagine.\n\n"
            "The genius of Minecraft is that it creates intrinsic motivation. You don't "
            "play Minecraft to beat it — there's a dragon and credits, but almost nobody "
            "cares. You play to build the castle you're imagining, to mine the resources "
            "for a more ambitious project, to survive one more night against the creepers.\n\n"
            "Education has embraced Minecraft in ways unprecedented for a commercial game. "
            "Teachers use it for mathematics (area and volume), history (building ancient "
            "civilizations), and collaborative project work. A version with specific "
            "educational tools — Minecraft Education Edition — has reached tens of millions "
            "of students. The game teaches spatial reasoning, systems thinking, and "
            "project management without calling any of it that."
        ),
    },
    # ── ENVIRONMENT / NATURE ──────────────────────────────────────────────────
    {
        "domain": "nationalgeographic.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "coral-reef-bleaching-what-it-means",
        "text": (
            "Coral bleaching happens when ocean temperatures rise even slightly above "
            "normal — by as little as 1-2°C sustained for a few weeks. The coral "
            "expels its symbiotic algae (zooxanthellae), which provide up to 90% of "
            "the coral's energy through photosynthesis. Without them, the coral turns "
            "ghostly white. It's not dead yet — bleached coral can recover if temperatures "
            "normalize quickly. But it's severely stressed.\n\n"
            "The Great Barrier Reef suffered mass bleaching events in 2016 and 2017 "
            "that killed more than 50% of the reef's shallow-water coral. A 2020 survey "
            "found bleaching had spread into deeper waters that had previously remained "
            "protected. Scientists described it as the most widespread bleaching event "
            "in the reef's recorded history.\n\n"
            "Coral reefs cover less than 1% of the ocean floor but support an estimated "
            "25% of all marine species. They protect coastlines from storm surge and "
            "erosion. They underpin fishing industries that feed hundreds of millions "
            "of people. The IPCC projects that 1.5°C of global warming will cause "
            "70-90% decline in coral reefs; at 2°C, greater than 99% loss."
        ),
    },
    {
        "domain": "audubon.org",
        "year_range": (2014, 2021),
        "content_type": "article",
        "url_slug": "backyard-bird-feeding-complete-guide",
        "text": (
            "Feeding wild birds is one of the most accessible connections to the natural "
            "world available to anyone with a backyard or even a window ledge. North "
            "Americans spend over four billion dollars annually on bird food — it's "
            "the second most popular outdoor hobby after gardening.\n\n"
            "Black oil sunflower seed is the universal currency of bird feeding: "
            "high oil content, thin shell, attractive to an enormous range of species. "
            "Cardinals, chickadees, finches, sparrows, nuthatches, and woodpeckers all "
            "eat it. If you only offer one food, make it this. Nyjer (thistle) seed "
            "specifically attracts goldfinches and siskins. Suet feeds woodpeckers "
            "and nuthatches through winter.\n\n"
            "Feeder placement matters for window collision prevention — the leading "
            "anthropogenic cause of bird death in North America after cats. Place "
            "feeders either within three feet of a window (too close for birds to "
            "build dangerous speed) or more than thirty feet away. Clean feeders "
            "regularly — wet, moldy seed spreads disease. Change water in birdbaths "
            "every one to two days."
        ),
    },
    # ── PSYCHOLOGY / SELF-HELP ────────────────────────────────────────────────
    {
        "domain": "psychologytoday.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "cognitive-behavioral-therapy-how-it-works",
        "text": (
            "Cognitive-behavioral therapy is the most rigorously studied form of "
            "psychotherapy. Meta-analyses across hundreds of randomized controlled "
            "trials show it's effective for depression, anxiety disorders, PTSD, "
            "OCD, eating disorders, and chronic pain management. The VA, NHS, and "
            "most national health bodies recommend it as a first-line treatment.\n\n"
            "The core insight: thoughts, feelings, and behaviors are interconnected. "
            "Negative automatic thoughts — 'I'll fail this exam,' 'She thinks I'm "
            "incompetent' — trigger emotional distress, which drives avoidance behaviors, "
            "which confirm the negative beliefs. The cycle sustains itself.\n\n"
            "CBT breaks the cycle at multiple points. Cognitive restructuring teaches "
            "patients to identify distorted thinking (catastrophizing, mind-reading, "
            "black-and-white thinking) and challenge it with evidence. Behavioral "
            "activation for depression involves scheduling pleasurable activities even "
            "when motivation is absent — action precedes mood improvement. Exposure "
            "therapy for anxiety involves gradual, systematic confrontation with feared "
            "situations, allowing the fear response to extinguish."
        ),
    },
    # ── SCIENCE / NATURE ──────────────────────────────────────────────────────
    {
        "domain": "scientificamerican.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "how-vaccines-work-immune-system",
        "text": (
            "Vaccines work by training your immune system to recognize a pathogen "
            "before you encounter it in nature. The training takes advantage of "
            "immunological memory — the immune system's ability to remember past "
            "invaders and respond faster and more powerfully on second exposure.\n\n"
            "Traditional vaccines introduce weakened or killed pathogens, or pieces "
            "of them (subunit vaccines), triggering an immune response without causing "
            "disease. The immune system produces antibodies and creates memory B and T "
            "cells. When the real pathogen arrives, the memory response clears it "
            "before disease can establish itself.\n\n"
            "mRNA vaccines, new to mass deployment in 2021, take a different approach. "
            "They deliver instructions for your cells to produce a specific protein "
            "(in COVID vaccines, the spike protein). Your immune system learns to "
            "recognize that protein and mounts a response. The mRNA degrades quickly "
            "and never enters the cell nucleus or interacts with DNA. The platform had "
            "been in development for twenty years before COVID accelerated deployment."
        ),
    },
    # ── FINANCE / PERSONAL FINANCE ────────────────────────────────────────────
    {
        "domain": "investopedia.com",
        "year_range": (2015, 2021),
        "content_type": "article",
        "url_slug": "index-fund-investing-beginners",
        "text": (
            "John Bogle's insight was simple and revolutionary: most actively managed "
            "funds underperform the market index after fees, over time. If you can't "
            "beat the market, own the market. An index fund holds every stock in an "
            "index proportionally — when the S&P 500 goes up 10%, your fund goes up "
            "approximately 10%, minus a tiny expense ratio.\n\n"
            "The data is unambiguous. The SPIVA report, published semiannually by "
            "S&P Global, tracks active fund performance against benchmarks. Over 15 years, "
            "roughly 90% of actively managed large-cap funds underperform their benchmark. "
            "The funds that outperform in one decade rarely repeat in the next.\n\n"
            "For most investors, a three-fund portfolio is sufficient: a total US market "
            "index fund, a total international index fund, and a bond index fund. "
            "Asset allocation between stocks and bonds depends on time horizon and "
            "risk tolerance — more stocks for longer horizons, more bonds as retirement "
            "approaches. Rebalance annually. Add money consistently, especially during "
            "downturns. Time in the market beats timing the market."
        ),
    },
    # ── GARDENING / HOME ──────────────────────────────────────────────────────
    {
        "domain": "gardeningknowhow.com",
        "year_range": (2013, 2021),
        "content_type": "article",
        "url_slug": "growing-tomatoes-backyard-garden",
        "text": (
            "Tomatoes are the most popular vegetable for home gardeners, and for good "
            "reason: a sun-warmed tomato from your own garden tastes nothing like a "
            "supermarket tomato. The difference is variety — commercial growers optimize "
            "for shelf life and firmness; home gardeners can choose for flavor.\n\n"
            "Site selection: tomatoes need minimum six hours of direct sun, with eight "
            "to ten being ideal. They're heavy feeders — amend soil with compost "
            "before planting. Start with transplants rather than seeds if you're a "
            "beginner; finding locally grown starts at a farmers market or nursery "
            "gives you varieties suited to your climate.\n\n"
            "The most common mistake: inconsistent watering. Irregular irrigation causes "
            "blossom end rot (calcium deficiency, not calcium lack in soil) and fruit "
            "cracking. Water deeply and consistently — drip irrigation is ideal. Mulch "
            "heavily around the base to retain moisture and prevent soil splash. "
            "Tomatoes are heavy feeders; side-dress with balanced fertilizer monthly "
            "or use a slow-release formulation at planting."
        ),
    },
]


def make_doc_id(url: str, timestamp: str) -> str:
    """Stable unique doc ID from URL and timestamp."""
    raw = f"{url}|{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def format_timestamp(year: int, month: int, day: int) -> str:
    """Format as FineWeb-style timestamp string."""
    return f"{year}{month:02d}{day:02d}120000"


def make_doc(template: dict, variation: int = 0) -> dict:
    """Generate one document from a template."""
    rng = random.Random(hash((template["url_slug"], variation)))
    year_lo, year_hi = template["year_range"]
    year = rng.randint(year_lo, year_hi)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    timestamp = format_timestamp(year, month, day)
    slug = template["url_slug"]
    if variation > 0:
        slug = f"{slug}-{variation}"
    url = f"https://{template['domain']}/{slug}"
    text = template["text"].strip()
    return {
        "id": make_doc_id(url, timestamp),
        "url": url,
        "text": text,
        "text_preview": text[:300],
        "timestamp": timestamp,
        "year": year,
        "domain": template["domain"],
        "word_count": len(text.split()),
        "content_type": template.get("content_type", "article"),
    }


def generate(count: int, output_path: Path) -> None:
    """Generate `count` documents and write to a single JSONL batch.

    Each template produces exactly ONE document — no duplicate text.
    If count exceeds templates, it is silently capped.
    """
    all_templates = ARTICLES + EXTRA_CONTENT + DIVERSE_TEMPLATES
    docs = []
    seen_ids: set[str] = set()

    for tmpl in all_templates:
        if len(docs) >= count:
            break
        doc = make_doc(tmpl)
        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            docs.append(doc)

    random.shuffle(docs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    domains = {d["domain"] for d in docs}
    content_types = {}
    for d in docs:
        ct = d["content_type"]
        content_types[ct] = content_types.get(ct, 0) + 1
    print(f"[seed] Wrote {len(docs)} documents to {output_path}")
    print(f"[seed] {len(domains)} unique domains")
    print(f"[seed] Content types: {content_types}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Generate dev seed dataset.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--output", type=str, default="data/raw/batch_000.jsonl")
    args = parser.parse_args()
    generate(args.count, Path(args.output))


if __name__ == "__main__":
    main()
