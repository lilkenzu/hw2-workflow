# Журнал инструментов

Только дополняется, старые записи не редактируются.

## 2026-08-28 · Сессия 1 · superpowers v6.3.0
- **Тип:** плагин Claude Code (набор скиллов + 1 хук)
- **Установка:**
  ```
  claude plugin marketplace add obra/superpowers-marketplace
  claude plugin install superpowers@superpowers-marketplace
  ```
- **Зачем:** методология разработки (brainstorming → план → TDD → code review →
  завершение ветки) поверх скиллов; готовый кандидат под обязательный пункт
  «Workflow» из ДЗ №2.
- **Проверка перед установкой:** прочитан README, `hooks/hooks.json`,
  `hooks/session-start`, `.claude-plugin/plugin.json`, `package.json` через
  GitHub API (без клонирования). 278 747 звёзд, 24 950 форков, MIT-лицензия,
  активно поддерживается (последний push 19.08.2026). Один хук `SessionStart`
  (matcher `startup|clear|compact`) — впрыскивает текст скилла
  `using-superpowers` в контекст, без сети, без записи файлов и без изменения
  git. Опциональная сетевая точка — логотип для visual companion в скилле
  `brainstorming` (версия пакета в query, отключается
  `SUPERPOWERS_DISABLE_TELEMETRY=1`).
- **Проверка после установки:** `claude plugin list` → `superpowers@superpowers-marketplace`,
  `Status: ✔ enabled`, scope `user`.

## 2026-08-28 · Сессия 1 · context-mode v1.0.169
- **Тип:** плагин Claude Code (MCP-сервер + 6 хуков)
- **Установка:**
  ```
  claude plugin marketplace add mksglu/context-mode
  claude plugin install context-mode@context-mode
  ```
- **Зачем:** оптимизация контекстного окна — сэндбокс-инструменты вместо сырого
  вывода в контекст, память сессии в SQLite/FTS5, автоматическая маршрутизация
  вызовов инструментов.
- **Проверка перед установкой:** README, `hooks/hooks.json`, `package.json`,
  `LICENSE`, `scripts/postinstall.mjs` через GitHub API. 20 202 звезды, 1466
  форков, но проект молодой (создан 23.02.2026, ~6 месяцев). **Существенно
  инвазивнее superpowers:** регистрирует `PreToolUse` (Bash/WebFetch/Read/Grep/
  Agent/все `mcp__`), `PostToolUse` (почти все инструменты), `UserPromptSubmit`
  (каждое сообщение пользователя), `Stop`, `PreCompact`, `SessionStart` — то
  есть проходит через весь трафик инструментов и промптов. Лицензия — Elastic
  License 2.0 (source-available, не MIT), в тексте упомянута «license key
  functionality», которую нельзя обходить — часть возможностей платная. Есть
  облачный компонент `context-mode.com/insight` («org analytics for
  AI-assisted engineering teams»), активируется явной командой `ctx_insight`.
  `postinstall.mjs` выполняется автоматически при установке (проверен —
  занимается только поправкой путей `better-sqlite3`/плагинов на конкретных
  платформах, сетевых вызовов не делает).
- **Решение:** риски озвучены пользователю явно (AskUserQuestion), пользователь
  выбрал полный вариант с хуками — «полный плагин с хуками (как в README)» —
  вместо более безопасного MCP-only варианта без хуков
  (`claude mcp add context-mode -- npx -y context-mode`).
- **Проверка после установки:** `claude plugin list` → `context-mode@context-mode`,
  `Status: ✔ enabled`, scope `user`. Функциональная проверка (`/context-mode:ctx-doctor`)
  отложена до следующей сессии — хуки активируются только при новом старте
  `claude`, эта сессия была запущена до установки.
