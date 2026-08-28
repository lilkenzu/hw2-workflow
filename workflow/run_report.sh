#!/usr/bin/env bash
# Точка входа. Два режима:
#   ./run_report.sh 29.07.2026 28.08.2026 [out.md]   — явный период
#   ./run_report.sh --last-month [out.md]             — автоматически весь прошлый календарный месяц
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "--last-month" ]; then
  read -r DATE_FROM DATE_TO < <(python3 -c "
import datetime
today = datetime.date.today()
first_this = today.replace(day=1)
last_month_end = first_this - datetime.timedelta(days=1)
last_month_start = last_month_end.replace(day=1)
print(last_month_start.strftime('%d.%m.%Y'), last_month_end.strftime('%d.%m.%Y'))
")
  OUT="${2:-$SCRIPT_DIR/report_$(date +%Y%m%d).md}"
else
  DATE_FROM="${1:?Использование: run_report.sh дд.мм.гггг дд.мм.гггг [out.md]  ИЛИ  run_report.sh --last-month}"
  DATE_TO="${2:?Использование: run_report.sh дд.мм.гггг дд.мм.гггг [out.md]}"
  OUT="${3:-$SCRIPT_DIR/report_$(date +%Y%m%d_%H%M).md}"
fi

set +e
python3 "$SCRIPT_DIR/cbr_report.py" \
  --date-from "$DATE_FROM" --date-to "$DATE_TO" \
  --currencies USD,EUR,CNY --out "$OUT"
STATUS=$?
set -e

case $STATUS in
  0) echo "Готово, находок нет: $OUT" ;;
  2) echo "Готово, ЕСТЬ находки, требующие внимания: $OUT" ;;
  *) echo "СБОЙ пайплайна (см. вывод выше), отчёт мог не сформироваться" >&2 ;;
esac
exit "$STATUS"
