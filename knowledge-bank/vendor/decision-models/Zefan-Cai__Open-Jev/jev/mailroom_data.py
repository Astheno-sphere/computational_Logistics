"""Original multilingual mailroom controls; no inbox, model, or routing fallback."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .api import compile_request
from .data import _hash, _write_dataset, split_group

VERSION = "mailroom-control-v1"
SOURCE_COMMIT = "06d44889231afb209e29275f14a529ba52c9eb0d"
SOURCE = "https://github.com/selcukusta/jev-mailroom/tree/" + SOURCE_COMMIT
SPLIT_POLICY = "Whole family includes translations, provider/payment/delivery counterfactuals and taxonomy variants. OOD iff index modulo ten >= 8, otherwise stable hash. Expansion preserves every earlier family."
LANGUAGES = ("en", "zh", "tr")
SERVICES = {
    "education": ("education", ("tuition supplied by the educational institution itself", "教育机构自身提供的学费服务", "eğitim kurumunun kendisinin sunduğu öğrenim hizmeti")),
    "electricity": ("electricity", ("electrical power supplied by the electricity utility itself", "电力供应商自身提供的电力供应服务", "elektrik tedarikçisinin kendisinin sağladığı elektrik enerjisi")),
    "telecom": ("telecom", ("mobile line service supplied by the telephone operator for a student's phone", "电话运营商为学生手机提供的移动通信服务", "telefon operatörünün bir öğrencinin telefonu için sağladığı mobil hat hizmeti")),
    "banking": ("banking", ("the bank's own annual card service fee", "银行自身收取的银行卡年费服务", "bankanın kendi yıllık kart hizmet ücreti")),
    "airline": ("airline", ("the airline's own checked-baggage service", "航空公司自身提供的托运行李服务", "hava yolu şirketinin kendi kayıtlı bagaj hizmeti")),
    "water": ("other", ("water supply from the water utility", "供水商提供的自来水供应服务", "su dağıtım şirketinin su temini hizmeti")),
    "insurance": ("other", ("an insurance policy supplied by the insurer", "保险公司提供的保险保单服务", "sigorta şirketinin sunduğu sigorta poliçesi")),
    "handset": ("other", ("a phone handset sold by a general retailer, without any telephone service", "普通零售商出售的手机硬件，不包含任何电话服务", "genel bir perakendecinin sattığı telefon cihazı; telefon hizmeti dahil değildir")),
    "purifier": ("other", ("air purifiers sold by a technology wholesaler", "技术批发商出售的空气净化器", "bir teknoloji toptancısının sattığı hava temizleme cihazları")),
    "equipment": ("other", ("electrical equipment sold by a hardware shop, without any power supply service", "五金商店出售的电气设备，不包含任何电力供应服务", "bir hırdavat mağazasının sattığı elektrikli ekipman; elektrik enerjisi tedariki dahil değildir")),
}
KIND_OPTIONS = {
    "invoice": "An issued bill, invoice, or charges statement. An announcement linking to an invoice is enough even if the email omits its amount.",
    "payment_confirmation": "Confirmation of money already paid or received, with no new demand for payment.",
    "account_statement": "A periodic bank/card activity summary, rather than an issued bill or payment receipt.",
    "promotion": "An offer, discount, or advertisement that sells something without asserting an existing debt.",
    "newsletter": "A recurring informational bulletin with no offer or money owed.",
    "other": "Other mail, such as shipping, appointments, or account-access notifications.",
}
CATEGORIES = {
    "education": "Education services billed by the educational institution; a student's telephone bill is not education.",
    "electricity": "Electrical power billed by its supplier; not water or electrical equipment sold by a shop.",
    "telecom": "Mobile or fixed telephone service billed by its operator; not a handset sold by a retailer.",
    "banking": "A financial institution's own account/card fees, interest or commissions; not a utility merely paid through a bank.",
    "airline": "An air carrier's own ticket, baggage, seat or flight service; not an agency or hotel.",
    "other": "A provider's bill for a service outside the named categories.",
}
TOPICS = {
    "education": "an educational institution or its educational services; not a student's unrelated telephone bill",
    "electricity": "an electricity supplier or supplied electrical power; not a hardware retailer's equipment",
    "telecom": "a telephone operator or mobile/fixed line service; not a retailer's handset",
    "banking": "a bank, payment card or financial institution's own products; not a utility merely paid through a bank",
    "airline": "an airline, flights, tickets or carrier services; not a hotel, agency or general retailer",
}


def questions(taxonomy="base"):
    """The source's 2 Choice + 9 Noul contract, independently worded."""
    if taxonomy not in ("base", "reordered", "insurance_added"):
        raise ValueError("Unknown mailroom taxonomy")
    categories = dict(CATEGORIES)
    if taxonomy == "reordered":
        categories = dict(reversed(list(categories.items())))
    elif taxonomy == "insurance_added":
        categories = {**{key: value for key, value in categories.items() if key != "other"},
                      "insurance": "An insurer's own insurance policy or premium.", "other": categories["other"]}
    result = {"kind": {"type": "choice", "instructions": "What is this email doing to the reader? Inspect email.subject and email.body. Judge the action, not merely its topic.", "criteria": KIND_OPTIONS},
              "states_amount_owed": {"type": "noul", "instructions": "Does email.body state a specific figure as money currently owed by the reader? Prices, savings, and already-paid amounts do not count."},
              "from_billing_entity": {"type": "noul", "instructions": "Comparing email.from and email.body, is this sender a provider issuing its own charges? A document relay, marketing message, or third party discussing another provider's charges is not."},
              "has_billing_identifiers": {"type": "noul", "instructions": "Does email.body contain an invoice/reference/account/customer number, billing period, or payment terms tying it to a specific account or charge? A parcel tracking number alone does not count."},
              "is_promotional": {"type": "noul", "instructions": "Is the purpose of email.subject and email.body to advertise an offer, with prices or savings rather than existing money owed?"},
              "category": {"type": "choice", "instructions": "What service is this bill charging for? Use the provider named in the subject/display name and the service in the body. An unfamiliar document-relay domain does not change the provider or service. Judge service, not payment status.", "criteria": categories}}
    for category, description in TOPICS.items():
        result["about_" + category] = {"type": "noul", "instructions": "Is the subject matter of this email " + description + "? Inspect email.from, email.subject and email.body. This concerns subject matter regardless of whether money is owed; promotions and newsletters can qualify."}
    return result


TEXT = {
    "en": {
        "service": "This message concerns {service}.",
        "own": "We, {company}, are the provider and issue our own charges.",
        "relay": "We are a document delivery service for {company}; we did not provide the billed service and these are not our own charges.",
        "invoice": "We have issued your invoice. Amount now owed: EUR {amount}.",
        "link": "Your issued invoice is available at https://documents.example/{code}. Open the invoice to see its amount; no amount is stated in this email.",
        "receipt": "Payment of EUR {amount} was already received. This is your payment receipt, with no new charges and nothing left to pay.",
        "promotion": "A promotional offer: buy now for EUR {amount} and save EUR 20. You have placed no order and owe nothing.",
        "newsletter": "Our monthly informational bulletin contains service news only, with no offer and no payment owed.",
        "account_statement": "Your periodic bank account activity statement is available. This is an activity summary, not an invoice or a payment receipt.",
        "shipping": "Your parcel has shipped. Tracking number: PK-{code}. This delivery notice contains no bill or payment receipt.",
        "reference": "Reference number: INV-{code}.",
        "account": "Account number: AC-{code}.",
        "bank_method": "You may pay via bank transfer; the bank is only a payment intermediary.",
        "subject": "{company} — service correspondence",
    },
    "zh": {
        "service": "本邮件涉及{service}。",
        "own": "我们是{company}，作为服务提供方开具自己的费用账单。",
        "relay": "我们是替{company}投递文件的平台；我们没有提供被计费的服务，这些不是我们自身的收费。",
        "invoice": "您的账单已开具。当前应付金额：EUR {amount}。",
        "link": "已开具的账单位于 https://documents.example/{code} 。请打开账单查看金额；本邮件没有列出金额。",
        "receipt": "我们已收到 EUR {amount} 的付款。这是付款收据，没有新收费，也没有任何剩余应付款。",
        "promotion": "促销优惠：现在购买价格为 EUR {amount}，可节省 EUR 20。您尚未下单，无需支付任何欠款。",
        "newsletter": "每月资讯简报仅包含服务新闻，没有促销优惠，也没有应付款。",
        "account_statement": "您的银行账户定期交易流水已可查看。这是活动汇总，不是账单，也不是付款收据。",
        "shipping": "您的包裹已经寄出。物流追踪号：PK-{code}。本配送通知不包含账单或付款收据。",
        "reference": "账单参考号：INV-{code}。",
        "account": "银行账号：AC-{code}。",
        "bank_method": "可通过银行转账付款；银行仅是支付中介。",
        "subject": "{company} — 服务往来邮件",
    },
    "tr": {
        "service": "Bu ileti {service} ile ilgilidir.",
        "own": "Biz, {company}, hizmet sağlayıcısı olarak kendi ücretlerimizi faturalandırıyoruz.",
        "relay": "{company} için belge iletim hizmetiyiz; faturalandırılan hizmeti biz sunmadık ve bunlar kendi ücretlerimiz değildir.",
        "invoice": "Faturanız düzenlendi. Şu anda ödenecek tutar: EUR {amount}.",
        "link": "Düzenlenmiş faturanız https://documents.example/{code} adresindedir. Tutarı görmek için faturayı açın; bu e-postada tutar belirtilmemiştir.",
        "receipt": "EUR {amount} ödemeniz zaten alındı. Bu ödeme makbuzudur; yeni ücret ve kalan borç yoktur.",
        "promotion": "Promosyon teklifi: şimdi EUR {amount} fiyatla alın ve EUR 20 tasarruf edin. Sipariş vermediniz ve borcunuz yoktur.",
        "newsletter": "Aylık bilgilendirme bültenimiz yalnızca hizmet haberleri içerir; teklif veya ödenecek borç yoktur.",
        "account_statement": "Dönemsel banka hesabı hareket dökümünüz hazır. Bu bir faaliyet özetidir, fatura veya ödeme makbuzu değildir.",
        "shipping": "Paketiniz gönderildi. Kargo takip numarası: PK-{code}. Bu teslimat bildirimi fatura veya ödeme makbuzu içermez.",
        "reference": "Fatura referans numarası: INV-{code}.",
        "account": "Hesap numarası: AC-{code}.",
        "bank_method": "Banka havalesiyle ödeyebilirsiniz; banka yalnızca ödeme aracısıdır.",
        "subject": "{company} — hizmet yazışması",
    },
}


def _email(code, language, service, variant, ood):
    language_index = LANGUAGES.index(language)
    text = TEXT[language]
    company = "Luma-" + code
    relay = variant in ("relay_invoice", "receipt")
    values = {"code": code, "company": company, "amount": str(120 + int(code[:4], 16) % 800) + ".40",
              "service": SERVICES[service][1][language_index]}
    parts = [text["service"]]
    if variant in ("invoice", "provider_counterfactual", "invoice_link", "relay_invoice", "receipt"):
        parts.append(text["relay" if relay else "own"])
    kind = {"invoice_link": "link", "relay_invoice": "invoice", "provider_counterfactual": "invoice"}.get(variant, variant)
    parts.append(text[kind])
    if variant in ("invoice", "relay_invoice", "provider_counterfactual", "receipt"):
        parts.append(text["reference"])
    if variant == "account_statement":
        parts.append(text["account"])
    if service == "electricity" and variant == "invoice":
        parts.append(text["bank_method"])
    if ood:
        parts = parts[2:] + parts[:2]
    address = ("relay@delivery-" if relay else "contact@luma-") + code + ".example"
    return {"email": {"subject": text["subject"].format(**values),
                       "from": {"display_name": "PaperRelay-" + code if relay else company,
                                "email": address, "domain": address.partition("@")[2]},
                       "date": "2026-09-20", "body": "\n".join(part.format(**values) for part in parts)}}


def generate(groups=10, seed=943):
    if type(groups) is not int or groups < 1:
        raise ValueError("groups must be a positive integer")
    cases, records, seen_inputs = [], [], {}
    variants = ("invoice", "invoice_link", "relay_invoice", "receipt", "promotion", "newsletter", "account_statement", "shipping", "provider_counterfactual")
    service_names = list(SERVICES)
    for index in range(groups):
        code = _hash([VERSION, seed, index])[:12]
        family = "mailroom:" + code
        ood = index % 10 >= 8
        split = "ood" if ood else split_group(family, seed)
        for language in LANGUAGES:
            for variant in variants:
                service = service_names[(index + (4 if variant == "provider_counterfactual" else 0)) % len(service_names)]
                if variant == "account_statement":
                    service = "banking"
                if variant == "shipping":
                    service = "purifier"
                state = _email(code, language, service, variant, ood)
                taxonomies = ("base", "reordered", "insurance_added") if language == "en" and variant == "invoice" else ("base",)
                for taxonomy in taxonomies:
                    case_id = family + ":" + language + ":" + variant + ":" + taxonomy
                    request = {"state": state, "questions": questions(taxonomy)}
                    kind = {"invoice_link": "invoice", "relay_invoice": "invoice", "provider_counterfactual": "invoice", "receipt": "payment_confirmation"}.get(variant, variant)
                    if kind == "shipping":
                        kind = "other"
                    category = SERVICES[service][0]
                    labels = {"kind": kind, "states_amount_owed": variant in ("invoice", "relay_invoice", "provider_counterfactual"),
                              "from_billing_entity": variant in ("invoice", "invoice_link", "provider_counterfactual"),
                              "has_billing_identifiers": variant in ("invoice", "relay_invoice", "provider_counterfactual", "receipt", "account_statement"),
                              "is_promotional": variant == "promotion"}
                    if kind in ("invoice", "payment_confirmation"):
                        labels["category"] = "insurance" if service == "insurance" and taxonomy == "insurance_added" else category
                    for topic in TOPICS:
                        labels["about_" + topic] = category == topic
                    case = {"id": case_id, "group_id": family, "split": split, "language": language,
                            "variant": variant, "taxonomy": taxonomy, "request": request, "reference_labels": labels,
                            "masked_questions": {} if "category" in labels else {"category": "No bill or payment receipt: charging-service question is inapplicable; no fallback label."},
                            "record_ids": [], "source": VERSION}
                    for compiled in compile_request(**request):
                        qid = compiled["id"]
                        if qid not in labels:
                            continue
                        target = [float(key == (str(labels[qid]).lower() if compiled["kind"] == "noul" else labels[qid])) for key in compiled["answer_keys"]]
                        input_key = _hash({key: compiled[key] for key in ("state", "question", "kind", "options")})
                        if input_key in seen_inputs:
                            case["record_ids"].append(seen_inputs[input_key])
                            continue
                        record_id = case_id + ":" + qid
                        seen_inputs[input_key] = record_id
                        records.append({"id": record_id, "group_id": family, "split": split, "source": VERSION,
                                        **{key: compiled[key] for key in ("state", "question", "kind", "options")}, "target": target,
                                        "metadata": {"family": "evidence", "template_id": VERSION + (":reordered_ood" if ood else ":normal_id"),
                                                     "case_id": case_id, "question_id": qid, "language": language,
                                                     "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                                                                    "group_index": index, "variant": variant + ":" + language + ":" + taxonomy,
                                                                    "license": "CC0-1.0", "split_policy": SPLIT_POLICY}}})
                        case["record_ids"].append(record_id)
                    cases.append(case)
    return cases, records


def build_dataset(output_dir, groups=10, seed=943):
    output = Path(output_dir)
    if output.is_symlink() or output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Choose a new empty mailroom directory; existing corpora are never overwritten")
    cases, rows = generate(groups, seed)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION, "groups": groups,
        "seed": seed, "license": "CC0-1.0", "source_interface": SOURCE,
        "source_code_or_emails_imported": False, "source_questions_sha256": "d9621c8ccdc9c8bf7dd8132a501390b3d15729a4ef8b1a821ae24d4c14bc5d1d",
        "source_triage_sha256": "b28e64711d2ebc53244fd1d85989158934e1fe0e6b1710294e40a60a3e259cf9",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "split_policy": SPLIT_POLICY,
        "ood_scope": "Unseen fictional families with reordered body paragraphs; finite controlled grammar, not unrestricted natural mail."})
    path = output / "cases.jsonl"
    path.write_text("".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n" for case in cases))
    manifest["files_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.update(request_cases=len(cases), language_counts=dict(Counter(case["language"] for case in cases)),
                    masked_category_cases=sum(bool(case["masked_questions"]) for case in cases),
                    questions_per_request=11, choice_questions=2, noul_questions=9,
                    model_inference_performed=False, training_performed=False, real_mail_imported=False,
                    supervision="Deterministic semantic labels from original controlled emails. Nonbill category omitted; no confidence, fallback, offline stub, or probability calibration labels.")
    manifest["deduplication"] = "Identical model inputs across taxonomy variants share the first row id; every request still contains all eleven questions. Case record_ids may reference a row emitted by an earlier case in the same family."
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups", type=int, default=10)
    parser.add_argument("--seed", type=int, default=943)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
