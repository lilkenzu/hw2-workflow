# Доказательства проверок

> Дополняет `sessions/session-1.md` — здесь только сырой вывод команд, без
> пересказа. Дата снятия: 2026-08-28.

## Проверка публичности репозитория (анонимный доступ, без токена/логина)

```bash
$ curl -s -o /dev/null -w "%{http_code}" https://github.com/lilkenzu/hw2-workflow
200
$ curl -s https://raw.githubusercontent.com/lilkenzu/hw2-workflow/main/README.md | head -5
# Курсы валют ЦБ РФ: аудит, риски, автоматизация
#
# ДЗ №2 · вариант **B1** («Курсы валют ЦБ: сбор, проверка, расхождения») ·
# агенты + workflow, курс «Занятие 2».
```

Оба запроса выполнены без какой-либо аутентификации — репозиторий публичный
и README читается со стороны.

## Проверка на секреты — расширенная, по 8 направлениям

Дата: 2026-08-28, после коммита `70469f7` (последний на момент проверки).

### 1. Ключи/токены/пароли по расширенным паттернам — рабочее дерево

```bash
$ grep -rniE "api[_-]?key|secret[_-]?key|password|passwd|bearer\s|-----BEGIN (RSA|OPENSSH|PRIVATE|EC|DSA)|ssh-rsa|ssh-ed25519|AKIA[0-9A-Z]{16}|xox[baprs]-|ghp_[a-zA-Z0-9]{36}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z_-]{35}" \
  . --exclude-dir=.git
# (пусто)
```

### 2. Файлы-кандидаты на секреты

```bash
$ find . -not -path './.git/*' \( -iname ".env*" -o -iname "settings.json" -o -iname "settings.local.json" \
  -o -iname "*.pem" -o -iname "*.key" -o -iname "id_rsa*" -o -iname "id_ed25519*" \
  -o -iname "*.p12" -o -iname "*.pfx" -o -iname "credentials*" -o -iname ".npmrc" -o -iname ".netrc" \)
# (пусто)
```

### 3. История команд / терминала

```bash
$ find . -not -path './.git/*' -iname "*.zsh_history*" -o -iname "*.bash_history*" -o -iname "*terminal*" -o -iname "*history*"
# (пусто)
```

### 4. Вся история git — не только текущее дерево

```bash
$ git log --oneline
70469f7 Обновить слайд 11: B1 — единственная тема, статус сдачи вместо открытых пунктов
3a71eb1 Закрыть чек-лист «Что сдавать»: REPORT.md, PDF-отчёт, замер параллельно/последовательно
6d6e373 ДЗ №2: вариант B1 — аудит курсов ЦБ, риски, workflow, презентация

$ for c in $(git rev-list --all); do
    git grep -niE "api[_-]?key|secret|password|-----BEGIN|ssh-rsa|ssh-ed25519|AKIA[0-9A-Z]{16}" "$c"
  done
# (пусто — ни в одном из 3 коммитов)
```

### 5. Файлы, когда-либо попадавшие в git (включая гипотетически удалённые)

```bash
$ git log --all --pretty=format: --name-only --diff-filter=A | sort -u | grep -v '^$'
```

Список из 25 файлов — совпадает ровно с текущим деревом. Ничего не было
закоммичено и потом убрано (что могло бы остаться в истории).

### 6. Метаданные PDF — не утекает ли локальный путь/имя пользователя

```bash
$ pdfinfo materials/presentation.pdf | grep -iE "creator|producer|title|author"
Title:    Курсы валют ЦБ РФ — презентация
Creator:  Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/151.0.0.0 Safari/537.36
Producer: Skia/PDF m151

$ pdfinfo materials/report-cbr-rates.pdf | grep -iE "creator|producer|title|author"
Title:    Отчёт: курсы валют ЦБ РФ
Creator:  Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/151.0.0.0 Safari/537.36
Producer: Skia/PDF m151
```

Только служебная строка Chrome headless (способ сборки PDF) — ни локального
пути, ни имени пользователя, ни автора.

### 7. Бинарный grep по PDF/PNG на локальный путь и имя пользователя

```bash
$ strings materials/presentation.pdf materials/report-cbr-rates.pdf materials/design_compare/*.png \
  | grep -i "nikita\|/Users/"
# (пусто)
```

### 8. Сырые данные ЦБ и open.er-api.com — только чистый ответ API

```bash
$ head -c 200 materials/daily_today.xml
<?xml version="1.0" encoding="windows-1251"?><ValCurs Date="28.08.2026" ...

$ head -c 200 materials/er_api.json
{"result":"success","provider":"https://www.exchangerate-api.com", ...
```

Ни в одном файле нет служебной обвязки `curl` (заголовков запроса, IP,
User-Agent отправителя) — только тело ответа сервера, как и было получено.

## Итог

Секретов, приватных ключей, паролей, токенов, файлов `.env`/`settings.json`,
истории команд — не найдено ни в рабочем дереве, ни в истории git, ни в
метаданных/бинарном содержимом PDF/PNG. Пункт чек-листа сдачи «проверьте
файлы на секреты» закрыт с доказательством, не на слово.
