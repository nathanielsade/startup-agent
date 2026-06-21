import json
from pathlib import Path

# (expected_name, slug-or-None) in companies.json index order, from the 10 resolver batches
PAIRS = [
    ("A.Team", "ateams"), ("Alchemy", None), ("Aleph", "aleph-vc"), ("Aligned", "alignedup"),
    ("Alpha Medical", "helloalphamd"), ("Anima", "anima-app"), ("AnyRoad", "anyroad"),
    ("Apiiro", "apiiro"), ("AppsFlyer", "appsflyer"), ("AppViewX", "appviewx"),
    ("Aqua Security", "aquasecteam"), ("Aquant", "aquant.io"), ("Arcadia", "arcadiahq"),
    ("Armis", "armis-security"), ("AST SpaceMobile", "ast-science"), ("Astra", "astraspace"),
    ("Atidot", "atidot"), ("Atom Computing", "atom-computing"), ("Augury", "augury-systems"),
    ("Axiom Zen", "axiom-zen"), ("Axonius", "axonius"), ("Azra Games", "azra-games"),
    ("Balbix", "balbix"), ("Base", "base-clg"), ("Battery Ventures", "battery-ventures"),
    ("BeeHero", "beehero"), ("Bessemer Venture Partners", "bessemer-venture-partners"),
    ("Biconomy", "biconomy"), ("Big Health", "big-health"), ("BioCatch", "biocatch"),
    ("Biolojic Design", "biolojic-design-ltd"), ("BIScience", "biscience"), ("Blink", "blink-ops"),
    ("Bloom", "bloominvest"), ("BlueGreen Water Technologies", "bluegreen-water-tech"),
    ("Bluewhite", "bluewhite"), ("Blumberg Capital", "blumberg-capital"), ("Bombas", "bombas"),
    ("Branch", "branch-metrics"), ("Brave Health", "brave-health"), ("Brinqa", "brinqa"),
    ("Candex", "candex-technologies"), ("Canopy", "canopy-care"), ("Capella Space", "capella-space"),
    ("Capitolis", "capitolis.com"), ("Carbon Health", "carbon-health"), ("Cato Networks", "cato-networks"),
    ("CB4", "c-b4-ltd"), ("Chainalysis", "chainalysis"), ("Chaos Labs", "chaos-labs-xyz"),
    ("Charles and Lynn Schusterman Family Philanthropies", "schustermanfamilyphilanthropies"),
    ("Codex", "usecodex"), ("CodiumAI", "qodoai"), ("ConsenSys", None), ("Constrafor", "constrafor"),
    ("Corelight", "corelight"), ("Cortica", "cortica-care"), ("Cybereason", "cybereason"),
    ("Cymulate", "cymulate"), ("Cynet", "cynet-security"), ("D-Fend Solutions", "d-fend-solutions"),
    ("DailyPay", "dailypay-inc"), ("Dandelion Energy", "dandelion-geothermal"), ("Dapper Labs", "dapper-labs"),
    ("Data.world", "data.world"), ("DataGrail", "datagrail"), ("Dataloop AI", "dataloop"),
    ("DataRails", "datarails"), ("Datree", "datreeio"), ("Decart.ai", "decart-ai"), ("Deel", "deel"),
    ("Didi", "didiglobal"), ("Docugami", "docugami"), ("DOT Compliance", "dot-compliance"),
    ("DTCP", "deutsche-telekom-capital-partners"), ("DustPhotonics", "dustphotonics"),
    ("EasySend", "easysend"), ("Edgybees", "edgybees-ltd"), ("eko", "ekovideo"), ("Eko", "eko-health"),
    ("Eleos Health", "eleoshealth"), ("Elvie", "elvie"), ("Emerge", "emerge-vc"), ("Empathy", "empathy"),
    ("Enigma Technologies", "enigma-technologies-inc-"), ("Epic Games", "epic-games"), ("Eternal", None),
    ("EvenUp", "evenup"), ("Explorium", "explorium-ai"), ("Firebolt", "firebolt"), ("Firefly", "fireflyon"),
    ("FloatMe", "floatme"), ("Flowcarbon", "flowcarbon"), ("Flox", "floxdev"), ("Forte", "forteplatform"),
    ("Forter", "forter"), ("Forum Brands", "forumbrands"), ("FreedomFi", "freedomfi"),
    ("General Atlantic", "general-atlantic"), ("Glooko", "glooko"), ("GoSource", "gosourcellc"),
    ("Grover", "grover"), ("Guesty", "guesty"), ("Hibob", "7586104"), ("HoneyBook", "honeybook"),
    ("HQ", "hqtravel"), ("HUMAN", "humansecurityinc"), ("Human Interest", "humaninterest"),
    ("Hyperscience", "hyperscience"), ("HYPR", "hyprcorp"), ("ICON", "icon3dtech"), ("Immuta", "immuta"),
    ("Insight Partners", "insight--partners"), ("ISEE", "isee-ai"), ("Jane Technologies", "jane-technologies-inc"),
    ("Jennifer Airobotics", "airobotics"), ("JetInsight", "jetinsight"), ("JFrog", "jfrog-ltd"),
    ("JumpCloud", "jumpcloud"), ("Juno", None), ("Kentik", "kentik"), ("Kraus Hamdani Aerospace", "kraus-aerospace"),
    ("Krypton", "kryptonexchange"), ("La Haus", "lahaus"), ("Latitude", "latitude-games"),
    ("LawGeex", "lawgeex"), ("Ledge", "ledge-finance"), ("Lightricks", "lightricks"),
    ("Lightspeed Financial Services", "lightspeed-financial"), ("LivePerson", "liveperson"),
    ("LucidLink", "lucidlink"), ("Lyft", "lyft"), ("Lyric", "lyric-tech"), ("MasterClass", "masterclassinc"),
    ("Medal", "medaltv"), ("Meron Capital", "meron-capital"), ("Mixtiles", None), ("Multiverse", None),
    ("Mysten Labs", None), ("N26", "n26"), ("Navina", "navina-ai"), ("Nexite", "nexiteio"), ("NFX", "nfxvc"),
    ("Nice", "nice"), ("NightDragon", "nightdragon-security"), ("Nirmata", "nirmata"), ("Noble", "noble-team"),
    ("NoTraffic", "notraffic"), ("Novidea", "novidea-software"), ("Obligo", "depositfree"),
    ("Offchain Labs", "offchain-labs-inc"), ("Oligo Security", "oligo-security"), ("Onapsis", "onapsis"),
    ("OnRamp", "team-onramp"), ("OpenLegacy", "openlegacy-inc"), ("OpenWeb", "openwebhq"), ("OPSWAT", "opswat"),
    ("Optimove", "optimove"), ("Orca Security", "orca-security"), ("Orchard", "orchardhomes"),
    ("Ordergroove", "ordergroove-inc."), ("Overline", "overline-vc"), ("OXIO", "oxiocorp"), ("Pagaya", "pagaya"),
    ("Palantir Technologies", "palantir-technologies"), ("Panorays", "panorays"), ("Paradox", "paradoxolivia"),
    ("Payoneer", "payoneer"), ("Peak", "peak-ai"), ("People.ai", "backstory-ai"), ("PlayVS", "playversus"),
    ("PointFive", "pointfive-us"), ("PrettyDamnQuick", "prettydamnquick"), ("Propel", "propel-crm"),
    ("PsiQuantum", "psiquantum-ltd"), ("Ramp", "rampnetwork"), ("RapidSOS", "rapidsos"),
    ("Ready Player Me", "readyplayerme"), ("Rec", None), ("Redefine Meat", "redefinemeat"),
    ("Reltio", "reltio-inc"), ("Riskified", "riskified"), ("Ro", "ro"), ("RocketReach", "rocketreach.co"),
    ("Saga Education", "sagaeducationorg"), ("Saga.xyz", "saga-xyz"), ("Sagetap", "sagetap"),
    ("Salt Security", "saltsecurity"), ("Samsung Next", "samsung-next"), ("Sauce", "getsaucedelivery"),
    ("Sayata", "sayatainsurance"), ("ScaleOps", "scaleops-sh"), ("Scopio Labs", "scopio-labs"),
    ("Sensi.AI", "sensi-ai"), ("SESO", "sesolabor"), ("Shield.", "shieldcommunicationcompliance"),
    ("Sidelines Group", "sidelinesio"), ("SignalWire", "signalwire"), ("Silverfort", "silverfort"),
    ("SimilarWeb", "similarweb"), ("Sisense", "sisense"), ("Skai", "skaicommerce"), ("SmartAsset", "smartasset-com"),
    ("SoFi", "sofi"), ("Space and Time", "space-and-time-db"), ("Storyblok", "storyblok"),
    ("Stream Security", "streamsecurity"), ("Stripe", "stripe"), ("super.AI", "mysuperai"),
    ("Superpedestrian", "superpedestrian-inc-"), ("Sweet Security", "sweet-security"), ("Swiftly", "swiftlyinc"),
    ("Swiftly", "swiftlysystems"), ("Sysdig", "sysdig"), ("Taboola", "taboola"), ("Tailor Brands", "tailor-brands"),
    ("Tala", "talamobile"), ("TAU Ventures", "tauventures"), ("Tavily", "tavily"), ("Terra", "terraapi"),
    ("The Garage", "thegaragevc"), ("Tomo", "tomonetworks"), ("Torii", "toriihq"), ("Torq", "torqio"),
    ("Tovala", "tovala"), ("TPG", "tpg-capital"), ("Travelier", "travelier-group"), ("TriEye", "trieye"),
    ("Tripledot Studios", "tripledot-studios"), ("Tymely AI", "tymelyinc"), ("Unit", "unit-finance"),
    ("Upstart", "upstart-network"), ("Vanta", "vanta-security"), ("Velocity", "techvelocity"),
    ("Veracode", "veracode"), ("Virtru", "virtru"), ("Volley", "volley"), ("Vonage (Israel)", "vonage"),
    ("Walnut", "teamwalnut"), ("Wilco", "trywilco"), ("Wiliot", "wiliot"), ("withco", "withco"),
    ("Wiz", "wizsecurity"), ("Yellowbrick Data", "yellowbrickdata"), ("Yotpo", "yotpo"), ("Zencity", "zencity"),
    ("zenity", "zenitysec"), ("Zesty", "zestyco"), ("Zimperium", "zimperium"),
]

path = Path("data/companies.json")
companies = json.loads(path.read_text())
assert len(companies) == len(PAIRS), f"count mismatch: {len(companies)} vs {len(PAIRS)}"

resolved = 0
for comp, (name, slug) in zip(companies, PAIRS):
    assert comp["name"] == name, f"order mismatch: {comp['name']!r} != {name!r}"
    if slug:
        comp["linkedin_url"] = f"https://www.linkedin.com/company/{slug}"
        resolved += 1
    else:
        comp["linkedin_url"] = None

path.write_text(json.dumps(companies, indent=2, ensure_ascii=False) + "\n")
print(f"OK: {resolved}/{len(companies)} resolved, {len(companies) - resolved} null")
