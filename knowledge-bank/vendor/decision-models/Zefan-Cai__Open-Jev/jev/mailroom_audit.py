"""Independent visible-text audit for mailroom-control-v1's finite grammar.

This is a corpus validator, not a language model or a general email classifier.
No generator templates, variant metadata, or reference labels determine answers.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from .api import compile_request

QUESTION_SHA = {
    "14b3baf63fae208c7b74dd645b85c087d49998aa13a049c9b679349cd8210632",
    "1cd0a3e8e3e07724c0edca24ef066ebe86521c64b3a7b2370be4a4f12ac5d15f",
    "9e55989861a7b4bf8b9f9320eeb88d705da6f5a6d39b65ab241ed1108f6c7633",
}
TOPICS = ("education", "electricity", "telecom", "banking", "airline")
SPLITS = ("train", "calibration", "validation", "test", "ood")
SERVICE_RULES = (
    ("education", r"tuition supplied by the educational institution itself|教育机构自身提供的学费服务|eğitim kurumunun kendisinin sunduğu öğrenim hizmeti"),
    ("electricity", r"electrical power supplied by the electricity utility itself|电力供应商自身提供的电力供应服务|elektrik tedarikçisinin kendisinin sağladığı elektrik enerjisi"),
    ("telecom", r"mobile line service supplied by the telephone operator for a student's phone|电话运营商为学生手机提供的移动通信服务|telefon operatörünün bir öğrencinin telefonu için sağladığı mobil hat hizmeti"),
    ("banking", r"the bank's own annual card service fee|银行自身收取的银行卡年费服务|bankanın kendi yıllık kart hizmet ücreti"),
    ("airline", r"the airline's own checked-baggage service|航空公司自身提供的托运行李服务|hava yolu şirketinin kendi kayıtlı bagaj hizmeti"),
    ("water", r"water supply from the water utility|供水商提供的自来水供应服务|su dağıtım şirketinin su temini hizmeti"),
    ("insurance", r"an insurance policy supplied by the insurer|保险公司提供的保险保单服务|sigorta şirketinin sunduğu sigorta poliçesi"),
    ("handset", r"a phone handset sold by a general retailer, without any telephone service|普通零售商出售的手机硬件，不包含任何电话服务|genel bir perakendecinin sattığı telefon cihazı; telefon hizmeti dahil değildir"),
    ("purifier", r"air purifiers sold by a technology wholesaler|技术批发商出售的空气净化器|bir teknoloji toptancısının sattığı hava temizleme cihazları"),
    ("equipment", r"electrical equipment sold by a hardware shop, without any power supply service|五金商店出售的电气设备，不包含任何电力供应服务|bir hırdavat mağazasının sattığı elektrikli ekipman; elektrik enerjisi tedariki dahil değildir"),
)
# Patterns describe observed text evidence; no variant id participates.
ACTION_RULES = (
    ("invoice", True, r"We have issued your invoice\. Amount now owed: EUR [0-9]+\.40\.|您的账单已开具。当前应付金额：EUR [0-9]+\.40。|Faturanız düzenlendi\. Şu anda ödenecek tutar: EUR [0-9]+\.40\."),
    ("invoice", False, r"Your issued invoice is available at https://documents\.example/[a-f0-9]{12}\. Open the invoice to see its amount; no amount is stated in this email\.|已开具的账单位于 https://documents\.example/[a-f0-9]{12} 。请打开账单查看金额；本邮件没有列出金额。|Düzenlenmiş faturanız https://documents\.example/[a-f0-9]{12} adresindedir\. Tutarı görmek için faturayı açın; bu e-postada tutar belirtilmemiştir\."),
    ("payment_confirmation", False, r"Payment of EUR [0-9]+\.40 was already received\. This is your payment receipt, with no new charges and nothing left to pay\.|我们已收到 EUR [0-9]+\.40 的付款。这是付款收据，没有新收费，也没有任何剩余应付款。|EUR [0-9]+\.40 ödemeniz zaten alındı\. Bu ödeme makbuzudur; yeni ücret ve kalan borç yoktur\."),
    ("promotion", False, r"A promotional offer: buy now for EUR [0-9]+\.40 and save EUR 20\. You have placed no order and owe nothing\.|促销优惠：现在购买价格为 EUR [0-9]+\.40，可节省 EUR 20。您尚未下单，无需支付任何欠款。|Promosyon teklifi: şimdi EUR [0-9]+\.40 fiyatla alın ve EUR 20 tasarruf edin\. Sipariş vermediniz ve borcunuz yoktur\."),
    ("newsletter", False, r"Our monthly informational bulletin contains service news only, with no offer and no payment owed\.|每月资讯简报仅包含服务新闻，没有促销优惠，也没有应付款。|Aylık bilgilendirme bültenimiz yalnızca hizmet haberleri içerir; teklif veya ödenecek borç yoktur\."),
    ("account_statement", False, r"Your periodic bank account activity statement is available\. This is an activity summary, not an invoice or a payment receipt\.|您的银行账户定期交易流水已可查看。这是活动汇总，不是账单，也不是付款收据。|Dönemsel banka hesabı hareket dökümünüz hazır\. Bu bir faaliyet özetidir, fatura veya ödeme makbuzu değildir\."),
    ("other", False, r"Your parcel has shipped\. Tracking number: PK-[a-f0-9]{12}\. This delivery notice contains no bill or payment receipt\.|您的包裹已经寄出。物流追踪号：PK-[a-f0-9]{12}。本配送通知不包含账单或付款收据。|Paketiniz gönderildi\. Kargo takip numarası: PK-[a-f0-9]{12}\. Bu teslimat bildirimi fatura veya ödeme makbuzu içermez\."),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_visible(request):
    """Read the final email and visible taxonomy, fail closed on unknown grammar."""
    qsha = hashlib.sha256(json.dumps(request["questions"], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    _require(qsha in QUESTION_SHA, "mailroom question contract changed")
    state = request["state"]
    _require(set(state) == {"email"}, "unexpected visible state fields")
    email = state["email"]
    _require(set(email) == {"subject", "from", "date", "body"}, "unexpected email fields")
    _require(set(email["from"]) == {"display_name", "email", "domain"}, "unexpected sender fields")
    _require(email["date"] == "2026-09-20", "unknown mailroom date grammar")
    code_match = re.match(r"Luma-([a-f0-9]{12}) — (service correspondence|服务往来邮件|hizmet yazışması)$", email["subject"])
    _require(code_match is not None, "unknown mailroom subject grammar")
    code = code_match[1]
    actions, services, roles = [], [], []
    identifiers = 0
    evidence = {}
    for line in email["body"].splitlines():
        service_match = re.fullmatch(r"This message concerns (.+)\.|本邮件涉及(.+)。|Bu ileti (.+) ile ilgilidir\.", line)
        if service_match:
            fragment = next(value for value in service_match.groups() if value)
            matches = [name for name, pattern in SERVICE_RULES if re.fullmatch(pattern, fragment)]
            _require(len(matches) == 1, "unknown or ambiguous service evidence")
            services.extend(matches)
            evidence["service"] = line
            continue
        matched = [(kind, owed) for kind, owed, pattern in ACTION_RULES if re.fullmatch(pattern, line)]
        if matched:
            actions.extend(matched)
            evidence["action"] = line
            continue
        own = rf"We, Luma-{code}, are the provider and issue our own charges\.|我们是Luma-{code}，作为服务提供方开具自己的费用账单。|Biz, Luma-{code}, hizmet sağlayıcısı olarak kendi ücretlerimizi faturalandırıyoruz\."
        relay = rf"We are a document delivery service for Luma-{code}; we did not provide the billed service and these are not our own charges\.|我们是替Luma-{code}投递文件的平台；我们没有提供被计费的服务，这些不是我们自身的收费。|Luma-{code} için belge iletim hizmetiyiz; faturalandırılan hizmeti biz sunmadık ve bunlar kendi ücretlerimiz değildir\."
        if re.fullmatch(own, line) or re.fullmatch(relay, line):
            roles.append("own" if re.fullmatch(own, line) else "relay")
            evidence["provider_role"] = line
            continue
        if re.fullmatch(rf"Reference number: INV-{code}\.|账单参考号：INV-{code}。|Fatura referans numarası: INV-{code}\.|Account number: AC-{code}\.|银行账号：AC-{code}。|Hesap numarası: AC-{code}\.", line):
            identifiers += 1
            evidence["identifier"] = line
            continue
        if re.fullmatch(r"You may pay via bank transfer; the bank is only a payment intermediary\.|可通过银行转账付款；银行仅是支付中介。|Banka havalesiyle ödeyebilirsiniz; banka yalnızca ödeme aracısıdır\.", line):
            continue
        raise ValueError("unrecognized mailroom body line")
    _require(len(actions) == len(services) == 1 and len(roles) <= 1 and identifiers <= 1, "ambiguous email facts")
    kind, owed = actions[0]
    service = services[0]
    _require(bool(roles) == (kind in ("invoice", "payment_confirmation")), "provider evidence incompatible with email action")
    _require(kind != "payment_confirmation" or roles == ["relay"], "receipt provider role is outside controlled grammar")
    relay_sender = roles == ["relay"]
    expected_address = ("relay@delivery-" if relay_sender else "contact@luma-") + code + ".example"
    _require(email["from"] == {"display_name": ("PaperRelay-" if relay_sender else "Luma-") + code,
                               "email": expected_address, "domain": expected_address.partition("@")[2]}, "header and provider evidence disagree")
    labels = {"kind": kind, "states_amount_owed": owed, "from_billing_entity": roles == ["own"],
              "has_billing_identifiers": bool(identifiers), "is_promotional": kind == "promotion"}
    if kind in ("invoice", "payment_confirmation"):
        options = request["questions"]["category"]["criteria"]
        labels["category"] = service if service in options else "other"
    labels.update({"about_" + topic: service == topic for topic in TOPICS})
    return {"labels": labels, "service": service, "evidence": evidence, "entity": "Luma-" + code}


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    _require(set(manifest["files_sha256"]) == {split + ".jsonl" for split in SPLITS} | {"cases.jsonl"}, "mailroom sealed file set differs")
    _require(all(sha(directory / name) == digest for name, digest in manifest["files_sha256"].items()), "manifest file hashes differ")
    cases = [json.loads(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
    rows = []
    for split in SPLITS:
        selected = [json.loads(line) for line in (directory / (split + ".jsonl")).read_text().splitlines()]
        _require(all(row["split"] == split for row in selected), "row stored in the wrong split file")
        rows.extend(selected)
    configuration = manifest["configuration"]
    expected_groups = {}
    for index in range(configuration["groups"]):
        raw = json.dumps(["mailroom-control-v1", configuration["seed"], index], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        family = "mailroom:" + hashlib.sha256(raw.encode()).hexdigest()[:12]
        split_raw = json.dumps([configuration["seed"], family], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        bucket = int(hashlib.sha256(split_raw.encode()).hexdigest()[:16], 16) % 10000
        assigned = next(name for bound, name in ((8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test")) if bucket < bound)
        expected_groups[family] = "ood" if index % 10 >= 8 else assigned
    _require(len(cases) == 29 * len(expected_groups), "incomplete family request coverage")
    _require(all(count == 29 for count in Counter(case["group_id"] for case in cases).values()), "incomplete family request coverage")
    row_map = {row["id"]: row for row in rows}
    _require(len(row_map) == len(rows) and len({case["id"] for case in cases}) == len(cases), "duplicate mailroom ids")
    visited, groups, entities, counts, mask_counts = set(), {}, {}, Counter(), Counter()
    for case in cases:
        parsed = parse_visible(case["request"])
        labels = parsed["labels"]
        _require(case["reference_labels"] == labels, "reference labels differ from visible email")
        _require(set(case["masked_questions"]) == ({"category"} if "category" not in labels else set()), "inapplicable category was not masked")
        _require(case["split"] in SPLITS, "unknown split")
        family, split = case["group_id"], case["split"]
        _require(family == "mailroom:" + parsed["entity"].removeprefix("Luma-"), "visible entity and family differ")
        _require(expected_groups.get(family) == split, "fixed family split assignment differs")
        _require(groups.setdefault(family, split) == split and entities.setdefault(parsed["entity"], split) == split, "family or entity crosses splits")
        mask_counts.update(case["masked_questions"].keys())
        expected_ids = []
        compiled_rows = [row for row in compile_request(**case["request"]) if row["id"] in labels]
        _require(len(case["record_ids"]) == len(compiled_rows), "case record coverage differs")
        for compiled, rid in zip(compiled_rows, case["record_ids"]):
            qid = compiled["id"]
            _require(rid in row_map, "missing mailroom row")
            row = row_map[rid]
            for key in ("state", "question", "kind", "options"):
                _require(row[key] == compiled[key], "compiled mailroom input differs")
            value = str(labels[qid]).lower() if compiled["kind"] == "noul" else labels[qid]
            target = [float(key == value) for key in compiled["answer_keys"]]
            _require(sum(target) == 1 and row["target"] == target, "target differs from visible email")
            _require(row["group_id"] == family and row["split"] == split, "row family or split differs")
            visited.add(rid)
            expected_ids.append(rid)
            counts[qid + ":" + str(labels[qid])] += 1
        _require(case["record_ids"] == expected_ids, "case record ids differ")
    _require(visited == set(row_map), "orphan mailroom rows")
    _require(groups == expected_groups, "family inventory differs")
    inputs = {json.dumps({key: row[key] for key in ("state", "question", "kind", "options")}, ensure_ascii=False, sort_keys=True) for row in rows}
    _require(len(inputs) == len(rows), "duplicate model inputs were not consolidated")
    return {"verified": True, "cases": len(cases), "records": len(rows), "groups": len(groups),
            "group_splits": dict(Counter(groups.values())), "languages": dict(Counter(case["language"] for case in cases)),
            "masked_questions": dict(mask_counts), "label_counts": dict(sorted(counts.items())),
            "unique_model_inputs": len(inputs), "model_inference_performed": False,
            "scope": "Independent finite-grammar audit from final visible body, sender and taxonomy; no claim of unrestricted semantic labeling.",
            "manifest_sha256": sha(directory / "manifest.json"), "auditor_sha256": sha(__file__)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    _require(not args.output.resolve().is_relative_to(args.data.resolve()), "write the audit outside the input data directory")
    _require(not args.output.exists(), "existing audit output is not overwritten")
    report = verify(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("verified", "cases", "records", "groups", "manifest_sha256")}, indent=2))


if __name__ == "__main__":
    main()
