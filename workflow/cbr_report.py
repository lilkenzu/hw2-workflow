#!/usr/bin/env python3
"""
cbr_report.py — единая точка входа: сбор данных ЦБ РФ по USD/EUR/CNY,
парсинг, аудит (дубликаты/пропуски/аномалии), сверка с open.er-api.com,
сборка markdown-отчёта для руководителя.

Запуск:
    python3 cbr_report.py --date-from 29.07.2026 --date-to 28.08.2026 \
        --currencies USD,EUR,CNY --out report.md

Зависимости: только стандартная библиотека Python 3.9+.
Exit codes: 0 = ок, находок нет; 2 = есть находки, требующие внимания;
            1 = сбой пайплайна (сеть/парсинг/конфигурация).
"""

import argparse
import datetime as dt
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CBR_DYNAMIC_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
CROSSCHECK_URL = "https://open.er-api.com/v6/latest/USD"

CURRENCY_CODES = {
    "USD": "R01235",
    "EUR": "R01239",
    "CNY": "R01375",
    # добавить сюда новую валюту — единственное место конфигурации
}

ANOMALY_THRESHOLD_PCT = 2.0      # день-к-дню, параметр, не хардкод в логике
CROSSCHECK_THRESHOLD_PCT = 1.0   # допустимое расхождение со вторым источником
HEADERS = {"User-Agent": "cbr-report-bot/1.0 (+internal reporting script)"}


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data:
        raise RuntimeError(f"Пустой ответ от {url}")
    return data


def parse_ru_date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%d.%m.%Y").date()


def fetch_dynamic(code: str, date_from: str, date_to: str) -> list[tuple[dt.date, float]]:
    """История курса за период. Кодировка cp1251, запятая->точка, Value/Nominal — ВСЕГДА."""
    url = f"{CBR_DYNAMIC_URL}?date_req1={date_from}&date_req2={date_to}&VAL_NM_RQ={code}"
    raw = http_get(url)
    text = raw.decode("cp1251")  # находка аудита #1: НЕ utf-8
    root = ET.fromstring(text)
    records = []
    for rec in root.findall("Record"):
        date_ = parse_ru_date(rec.attrib["Date"])
        nominal = int(rec.findtext("Nominal", "1").replace(" ", ""))
        value_raw = rec.findtext("Value", "").strip()
        if not value_raw:
            continue
        try:
            value = float(value_raw.replace(",", "."))  # находка аудита #2: запятая -> точка
        except ValueError:
            print(f"ПРЕДУПРЕЖДЕНИЕ: не удалось распарсить Value='{value_raw}' "
                  f"для {code} на {date_}", file=sys.stderr)
            continue
        rate = value / nominal  # находка аудита #3: делим на Nominal ВСЕГДА, без исключений
        records.append((date_, rate))
    records.sort(key=lambda x: x[0])
    return records


def fetch_daily_snapshot() -> dict[str, float]:
    """Срез курсов ЦБ на сегодня — независимая проверка того же API другим эндпоинтом."""
    raw = http_get(CBR_DAILY_URL)
    text = raw.decode("cp1251")
    root = ET.fromstring(text)
    result = {}
    for valute in root.findall("Valute"):
        char_code = valute.findtext("CharCode")
        nominal = int(valute.findtext("Nominal", "1"))
        value = float(valute.findtext("Value", "0").replace(",", "."))
        result[char_code] = value / nominal
    return result


def business_days(d1: dt.date, d2: dt.date) -> list[dt.date]:
    days, d = [], d1
    while d <= d2:
        if d.weekday() < 5:  # Пн-Пт
            days.append(d)
        d += dt.timedelta(days=1)
    return days


@dataclass
class CurrencyAudit:
    code: str
    records: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    missing_expected: list = field(default_factory=list)     # понедельник после пятницы — норма
    missing_unexplained: list = field(default_factory=list)  # реальный пропуск
    anomalies: list = field(default_factory=list)


def audit_currency(code: str, records: list[tuple[dt.date, float]],
                    date_from: dt.date, date_to: dt.date) -> CurrencyAudit:
    audit = CurrencyAudit(code=code, records=records)

    # Дубликаты дат
    seen: dict[dt.date, list[float]] = {}
    for d, v in records:
        seen.setdefault(d, []).append(v)
    audit.duplicates = [d for d, vs in seen.items() if len(vs) > 1]

    # Пропуски будних дат — с бизнес-правилом ЦБ (находка аудита #4)
    present = set(d for d, _ in records)
    for d in business_days(date_from, date_to):
        if d in present:
            continue
        if d.weekday() == 0 and (d - dt.timedelta(days=3)) in present:
            audit.missing_expected.append(d)   # пятница есть -> понедельник не публикуется, это норма
        else:
            audit.missing_unexplained.append(d)

    # Аномалии >порога, день-к-дню по ФАКТИЧЕСКИ ИМЕЮЩИМСЯ соседним записям
    for i in range(1, len(records)):
        d_prev, v_prev = records[i - 1]
        d_cur, v_cur = records[i]
        if v_prev == 0:
            continue
        pct = (v_cur - v_prev) / v_prev * 100
        if abs(pct) > ANOMALY_THRESHOLD_PCT:
            audit.anomalies.append((d_prev, d_cur, v_prev, v_cur, pct))

    return audit


def fetch_crosscheck() -> dict[str, float]:
    """USD/RUB напрямую, EUR/RUB и CNY/RUB через кросс-курс к USD."""
    raw = http_get(CROSSCHECK_URL)
    data = json.loads(raw.decode("utf-8"))
    if data.get("result") != "success":
        raise RuntimeError("open.er-api.com вернул неуспешный результат")
    rates = data["rates"]
    return {
        "USD": rates["RUB"],
        "EUR": rates["RUB"] / rates["EUR"],
        "CNY": rates["RUB"] / rates["CNY"],
    }


def build_report(audits: dict[str, CurrencyAudit], crosscheck: dict[str, float],
                  daily_check_note: str, date_from: dt.date, date_to: dt.date) -> str:
    L = []
    L.append(f"# Отчёт по курсам ЦБ РФ ({date_from:%d.%m.%Y} – {date_to:%d.%m.%Y})")
    L.append("")
    L.append(f"_Сгенерировано автоматически: {dt.datetime.now():%d.%m.%Y %H:%M}_")
    L.append("")
    L.append("## Дубликаты и пропуски")
    L.append("")
    for code, a in audits.items():
        dup = f" ({', '.join(d.strftime('%d.%m') for d in a.duplicates)})" if a.duplicates else ""
        miss = f" ({', '.join(d.strftime('%d.%m') for d in a.missing_unexplained)})" if a.missing_unexplained else ""
        L.append(f"**{code}**: дубликатов — {len(a.duplicates)}{dup}; "
                  f"ожидаемых пропусков (пн после пятничного курса) — {len(a.missing_expected)}; "
                  f"**необъяснённых пропусков — {len(a.missing_unexplained)}{miss}**.")
    L.append("")
    L.append(f"## Аномалии (изменение >{ANOMALY_THRESHOLD_PCT}% день-к-дню)")
    L.append("")
    L.append("| Валюта | Период | Было | Стало | Δ% |")
    L.append("|---|---|---|---|---|")
    any_anomaly = False
    for code, a in audits.items():
        for d_prev, d_cur, v_prev, v_cur, pct in a.anomalies:
            any_anomaly = True
            L.append(f"| {code} | {d_prev:%d.%m} → {d_cur:%d.%m} | {v_prev:.4f} | {v_cur:.4f} | {pct:+.2f}% |")
    if not any_anomaly:
        L.append("| — | — | — | — | аномалий не найдено |")
    L.append("")
    L.append("## Сверка со вторым источником (open.er-api.com, последняя дата периода)")
    L.append("")
    if crosscheck:
        L.append("| Валюта | ЦБ РФ | open.er-api.com | Расхождение | Статус |")
        L.append("|---|---|---|---|---|")
        for code, a in audits.items():
            if not a.records or code not in crosscheck:
                continue
            _, last_val = a.records[-1]
            ref_val = crosscheck[code]
            diff_pct = abs(last_val - ref_val) / ref_val * 100
            status = "OK" if diff_pct <= CROSSCHECK_THRESHOLD_PCT else f"ПРЕВЫШЕНИЕ ПОРОГА {CROSSCHECK_THRESHOLD_PCT}%"
            L.append(f"| {code}/RUB | {last_val:.4f} | {ref_val:.4f} | {diff_pct:.2f}% | {status} |")
    else:
        L.append("_Сверка недоступна: второй источник не ответил (см. лог запуска)._")
    L.append("")
    if daily_check_note:
        L.append("## Доп. проверка согласованности API ЦБ")
        L.append("")
        L.append(daily_check_note)
        L.append("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date-from", required=True, help="дд.мм.гггг")
    p.add_argument("--date-to", required=True, help="дд.мм.гггг")
    p.add_argument("--currencies", default="USD,EUR,CNY")
    p.add_argument("--out", default="report.md")
    args = p.parse_args()

    date_from, date_to = parse_ru_date(args.date_from), parse_ru_date(args.date_to)
    currencies = [c.strip().upper() for c in args.currencies.split(",")]

    audits: dict[str, CurrencyAudit] = {}
    for cur in currencies:
        code = CURRENCY_CODES.get(cur)
        if not code:
            print(f"ОШИБКА: неизвестный код валюты {cur} (добавь в CURRENCY_CODES)", file=sys.stderr)
            sys.exit(1)
        try:
            records = fetch_dynamic(code, args.date_from, args.date_to)
        except Exception as e:
            print(f"ОШИБКА при получении/парсинге {cur}: {e}", file=sys.stderr)
            sys.exit(1)
        if not records:
            print(f"ОШИБКА: нет данных по {cur} за период", file=sys.stderr)
            sys.exit(1)
        audits[cur] = audit_currency(cur, records, date_from, date_to)

    try:
        crosscheck = fetch_crosscheck()
    except Exception as e:
        print(f"ПРЕДУПРЕЖДЕНИЕ: сверка со вторым источником недоступна: {e}", file=sys.stderr)
        crosscheck = {}

    daily_note = ""
    if date_to == dt.date.today():
        try:
            snapshot = fetch_daily_snapshot()
            mismatches = []
            for cur, a in audits.items():
                if not a.records:
                    continue
                _, last_val = a.records[-1]
                snap_val = snapshot.get(cur)
                if snap_val is not None and abs(last_val - snap_val) > 1e-4:
                    mismatches.append(f"{cur}: dynamic={last_val:.4f} vs daily={snap_val:.4f}")
            daily_note = ("Расхождений между XML_dynamic и XML_daily не найдено."
                           if not mismatches else
                           "Расхождение между эндпоинтами ЦБ: " + "; ".join(mismatches))
        except Exception as e:
            daily_note = f"Доп. проверка через XML_daily.asp не выполнена: {e}"

    report = build_report(audits, crosscheck, daily_note, date_from, date_to)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Отчёт сохранён: {args.out}")

    has_issues = any(a.missing_unexplained or a.anomalies for a in audits.values())
    sys.exit(2 if has_issues else 0)


if __name__ == "__main__":
    main()
