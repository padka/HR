# RecruitSmart Unified Redesign Strategy

Дата: 2026-04-19  
Статус: implementation-ready strategy artifact  
Язык документа: русский  
Область: `/app/*`, `/tg-app/*`, bounded `/miniapp`

## Основание
- PRT: `/Users/mikhail/Desktop/RecruitSmart_Unified_Design_PRT_2026-04-19.pdf`
- Canonical frontend docs:
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/README.md`
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/design-system.md`
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/screen-inventory.md`
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/route-map.md`
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/state-flows.md`
  - `/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/component-ownership.md`
- Mounted runtime truth and module ownership:
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidates.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/messenger/MessengerPage.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/login.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/dashboard.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/index.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/incoming.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/candidate.tsx`
  - `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/miniapp/index.tsx`

## Правило интерпретации
- PRT считается target direction.
- Live code и canonical docs считаются truth для текущего mounted runtime.
- Все implementation-level уточнения, которых нет буквально в PRT, даны как operational extension для дизайн-команды и frontend-команды.
- Документ не предлагает backend-heavy redesign, не описывает unsupported candidate browser portal как live UI и не трактует bounded MAX pilot как full production rollout.

# A. Executive reinterpretation

## Что это за продукт
RecruitSmart должен восприниматься не как набор страниц CRM, а как единая операционная среда рекрутера для high-volume early-stage hiring. Продукт нужен не для полного HR-cycle и не для презентации бренда работодателя. Его задача проще и жестче: быстро принять входящий поток, понять состояние кандидата, удержать темп коммуникации, выбрать следующий шаг и довести человека до интервью без потери контекста.

## Основные пользователи
| Пользователь | Рабочая цель | Частота работы | Главный риск |
| --- | --- | --- | --- |
| Рекрутер | Разобрать очередь, написать кандидату, назначить слот, сдвинуть статус | Очень высокая | Потеря скорости из-за перегруженного UI |
| Руководитель рекрутинга | Видеть очереди, пропускную способность, зоны риска, нагрузку команды | Средняя/высокая | KPI видны, но actionability размыта |
| Администратор | Поддерживать справочники, шаблоны, настройки и доступы | Средняя | CRUD выглядит как отдельный продукт |
| Кандидат в MAX mini app | Пройти тест, выбрать время, понять следующий шаг | Ситуативная | CRM-терминология и слабая прозрачность статуса |

## Primary jobs-to-be-done
- Быстро понять, кто требует первого касания прямо сейчас.
- Найти кандидата и за секунды увидеть его stage, urgency, channel, owner и next action.
- Продолжить коммуникацию без переключения в другой ментальный режим.
- Подобрать и подтвердить слот без борьбы с фильтрами и лишним chrome.
- Не терять кандидата между Telegram, MAX и SPA из-за разной семантики статусов и действий.

## Самые частые действия
- Поиск и фильтрация очереди кандидатов.
- Открытие candidate detail и принятие следующего действия.
- Отправка сообщения или шаблонного ответа.
- Назначение, перенос или подтверждение слота.
- Изменение stage и фиксация outcome.
- Проверка статуса возвратов, перегрузки, overdue и риска потери.

## Самые критичные экраны
- `/app/candidates`
- `/app/candidates/$candidateId`
- `/app/dashboard`
- `/app/slots`
- `/app/messenger`
- `/tg-app/incoming`
- `/tg-app/candidates/$candidateId`
- `/miniapp` как единый bounded candidate journey

## Где сейчас возникает когнитивная перегрузка
- В списках и scheduling screens слишком много controls до начала данных.
- В candidate detail много модулей, но слабая первая смысловая сцена.
- Messaging split между `/app/messenger` и `CandidateChatDrawer` не оформлен как один workflow.
- `/app/login` и protected-route auth states не дают достаточно ясного outcome.
- Telegram surface говорит на более бедном визуальном и смысловом языке, чем основной SPA.
- MAX mini app уже ближе к candidate-first UX, но живет в отдельной token/visual реальности.

## Главная единица интерфейса
Главной единицей интерфейса должен стать не экран и не карточка, а candidate work item:
- кто это;
- где он находится;
- что требует внимания;
- какой следующий шаг доминирует;
- через какой канал разумнее продолжать;
- кто владелец;
- есть ли риск потерять кейс.

Эта единица должна одинаково читаться:
- в строке списка;
- в queue card;
- в candidate detail header;
- в TG triage card;
- в MAX candidate state card.

## Характер интерфейса RecruitSmart
Интерфейс должен быть спокойным, дисциплинированным, operational-first и премиальным за счет ясности, а не за счет декоративности. Это не “luxury dashboard” и не generic SaaS. Это быстрый рабочий cockpit, где:
- content сильнее chrome;
- action сильнее decoration;
- hierarchy сильнее спецэффектов;
- continuity сильнее page-by-page визуального разнобоя.

## Current system constraints
- Live mounted runtime включает `/app/*`, `/tg-app/*` и bounded `/miniapp`.
- Standalone candidate browser portal не является текущей live surface.
- `/miniapp` является bounded pilot surface, default-off и controlled-pilot only.
- Telegram остается единственным live messaging runtime сегодня; MAX candidate mini app использует bounded handoff, а не full messaging rollout.
- Shared candidate journey, Test1, booking и handoff semantics остаются canonical; MAX не должен форкать бизнес-логику.
- Документ ниже проектирует единый UX-язык поверх текущей архитектуры, а не новый продуктовый backend.

# B. Design vision

## Design manifesto
1. **Action first.** На каждом recruiter-facing экране должен быть один доминирующий next action.
2. **Content over chrome.** Данные, статус и коммуникация важнее визуальной оболочки.
3. **Calm density.** Плотность допустима, если сохраняются scan speed и семантическая ясность.
4. **Semantics before cosmetics.** Stage, urgency, risk, channel, owner и next action нельзя смешивать ни цветом, ни формой.
5. **One product, adapted shells.** SPA, Telegram и MAX не копируют друг друга, но говорят на одном UI-языке.
6. **Continuity, not spectacle.** Motion объясняет состояние и переход, а не развлекает.
7. **Mobile is not a compressed desktop.** TG и mobile states проектируются как самостоятельные композиции.
8. **Guidance without clutter.** Подсказки даются через контекст, card grammar и local feedback, а не через постоянные help-блоки.
9. **Human clarity for candidates.** Candidate-facing states переводят внутреннюю HR-логику в понятный человеческий язык.

## Визуальная философия
RecruitSmart должен перейти от “тёмной премиальности как атмосферы” к “спокойной рабочей среде как системе”. Визуальная дороговизна достигается не большим количеством эффектов, а:
- точной типографикой;
- ясной глубиной поверхностей;
- дисциплиной статусов;
- уверенными интервалами;
- контролируемым contrast budget;
- материалами, у которых есть функция.

Правило базового визуального языка:
- glass живет в chrome и control layers;
- solid живет в data layers;
- elevated surfaces помогают группировать решения;
- page background остается тихим и не спорит с данными.

## Interaction philosophy
Работа рекрутера должна ощущаться как непрерывное ведение кейсов, а не как прыжки между несвязанными экранами. Поэтому:
- список должен вести в detail как следующий слой того же объекта;
- detail должен вести в messaging, scheduling и stage-change без потери контекста;
- local actions подтверждаются рядом с источником действия;
- фильтры, search и saved views должны служить ускорению, а не становиться отдельной задачей.

Кандидатный опыт в MAX должен ощущаться иначе по тону, но не по логике:
- меньше внутренней терминологии;
- больше объяснения “что происходит сейчас” и “что будет дальше”;
- всегда виден fallback.

## Где glass и layered materials уместны
| Материал | Где разрешен | Где запрещен | Функция |
| --- | --- | --- | --- |
| Chrome Glass | top bars, floating filter bars, compact nav, toolbar search, small overlays | data tables, dense forms, message transcripts, timeline body | Отделить controls от content без тяжелого блока |
| Overlay Glass | modal backdrop, lightweight side sheet header, contextual popover | base page panels, long-scroll bodies | Подчеркнуть слой поверх уже понятного контента |
| Soft Elevated Surface | queue cards, decision cards, contextual summary blocks | long data grids, dense editable areas | Выделить решение или состояние выше соседей |
| Solid Data Surface | candidate body, forms, tables, chat, notes, scheduling blocks | не запрещен; это default | Максимальная читаемость и стабильность |

## Где glass использовать нельзя
- В формах, где требуется серия точных вводов.
- В длинных таблицах и списках.
- В основном message transcript.
- В candidate detail body, если это снижает contrast.
- В Telegram shell и low-end mobile contexts, где blur бьет по performance.

## Как должен ощущаться продукт
Для рекрутера:
- “Я быстро вижу, кто важнее.”
- “Я не декодирую интерфейс, а веду поток.”
- “Следующий шаг очевиден.”
- “Я не теряю контекст при переходе между списком, кандидатом, перепиской и слотами.”

Для кандидата:
- “Я понимаю, где нахожусь.”
- “Сервис объясняет следующий шаг человеческим языком.”
- “Если автоматический путь закончился, я знаю, как продолжить.”

# C. Design system foundation

## C.1 Foundation direction
Current runtime уже имеет token system, dark baseline, light theme и отдельный `liquid-glass-v2` mode, но foundation фрагментирован между SPA, Telegram и MAX. Target foundation должен стать единым semantic layer поверх трех shell adapters.

| Слой | Current runtime | Target direction |
| --- | --- | --- |
| Typographic base | SPA: `Manrope` + `Space Grotesk`; TG/MAX ближе к system/native | `Inter Variable` как рабочая гарнитура; `system-ui` fallback в TG/MAX при перф-ограничениях |
| Surface model | glass-heavy SPA, native-like TG, separate MAX tokens | one semantic material stack with shell-specific rendering |
| Status grammar | partially shared, visually inconsistent | one badge/state contract across all shells |
| Motion | tokens есть, но опыт фрагментирован | utility-first motion system with continuity rules |
| Dense data patterns | list/card/kanban coexist, hierarchy uneven | explicit table/list/card decision model |

## C.2 Typography system

### Recommended font strategy
- Основная рабочая гарнитура: `Inter Variable`.
- Fallback stack для web: `Inter Variable`, `Inter`, `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`.
- TG/MAX fallback: `system-ui` допустим без изменения scale и hierarchy, если webfont ухудшает startup/perf.
- `Space Grotesk` не использовать как постоянный display layer в operational UI.

### Type scale
| Token | Size / line-height / weight | Usage |
| --- | --- | --- |
| `display-xl` | `32 / 38 / 650` | редкие hero zones, не больше одного раза на экране |
| `page-title` | `26 / 32 / 650` | основные экраны: Dashboard, Candidates, Candidate Detail |
| `section-title` | `20 / 26 / 600` | крупные секции и панели |
| `card-title` | `16 / 22 / 600` | queue cards, decision cards, compact panels |
| `body` | `14 / 20 / 450` | основной текст интерфейса |
| `body-dense` | `13 / 18 / 450` | строки таблиц, вторичная мета, compact list rows |
| `caption` | `12 / 16 / 500` | helper, timestamps, пояснения |
| `badge-label` | `11 / 14 / 600` | stage, channel, urgency, risk badges |
| `button-label` | `14 / 18 / 600` | CTA, toolbar actions |
| `numeric-kpi` | `28 / 32 / 650` | dashboard counts, queue counters, SLA numbers |

### Optical hierarchy rules
- На экране один `page-title`, не несколько competing hero blocks.
- `section-title` используется для layout grouping, а не для каждого модульного контейнера.
- `card-title` нужен только там, где у card есть самостоятельный смысл.
- `body-dense` допустим в таблицах и compact cards, но не в primary CTA zones.
- `caption` не должен быть основным носителем критичной информации.
- Field labels всегда над полем и всегда семантически связаны с input.
- All caps не использовать для navigation, stage и state labels; исключение только для очень коротких technical tags.

### Dense operational screen rules
- В строке списка только один сильный текстовый якорь: identity или dominant next action.
- Secondary meta опускается на меньший контраст и меньший размер.
- В dark mode `caption` и small meta нельзя опускать до “эффектно, но нечитаемо”.
- Form sections используют `card-title` только для реальных смысловых блоков, не для декоративного разделения.

### Numeric and data typography
- KPI, counters, slot times, SLA, queue counts, response time используют tabular numerals.
- Числа в KPI всегда в один визуальный слой с коротким контекстным label.
- В таблицах numeric columns выравнивать оптически и не смешивать с badges в одном визуальном ряду.

## C.3 Color system

### Neutral and semantic palette
| Role | Dark | Light | Usage |
| --- | --- | --- | --- |
| Canvas primary | `#0B1020` | `#F4F7FB` | quiet page background |
| Canvas secondary | `#0E1528` | `#EEF2F7` | shell underlay, large zones |
| Surface solid | `#121A2B` | `#FFFFFF` | forms, tables, chat, timeline |
| Surface elevated | `#172239` | `#F7FAFD` | decision blocks, queue cards |
| Surface glass tint | `rgba(12,18,32,0.68)` | `rgba(255,255,255,0.76)` | chrome/toolbars/overlays |
| Border subtle | `rgba(255,255,255,0.08)` | `rgba(15,23,42,0.08)` | standard boundaries |
| Border strong | `rgba(255,255,255,0.16)` | `rgba(15,23,42,0.14)` | focus, active, grouped separation |
| Text primary | `#F6F8FB` | `#0F172A` | critical text |
| Text secondary | `#C7D0DE` | `#42526B` | labels, secondary value text |
| Text tertiary | `#97A4B7` | `#67758C` | timestamps, less important meta |
| Accent primary | `#4F7CFF` | `#295EFF` | primary CTA, selected state |
| Success | `#2FCB7C` | `#0E9F5B` | confirmed, booked, delivered |
| Warning | `#F2B24A` | `#B97407` | reply due, deadline near, partial block |
| Danger | `#FF6B6B` | `#D14343` | failed, blocked, destructive |
| Info | `#50B8FF` | `#0E8BD8` | informative system states |

### Semantic usage rules
- Accent отвечает за selected/current/actionable, а не за любой “важный” цвет.
- Success используется только для подтвержденного progress или выполненного шага.
- Warning сигнализирует о времени, нехватке ответа или soft block.
- Danger оставлять для hard block, failure, destructive actions и критических delivery issues.
- Channel colors допустимы только как origin marker внутри channel badge, message header или integration marker.
- Смысл нельзя кодировать только цветом; нужен label, icon или structural cue.

### Contrast rules
- Минимум `4.5:1` для текстовых пар; целевой уровень для рабочего текста в dark mode ближе к `7:1`.
- Non-text indicators минимум `3:1`.
- Small text, chips и timestamps проверять на реальном dark monitor и на mobile, а не только в Figma preview.

### Light / dark behavior
- Light и dark используют одинаковую hierarchy model и component grammar.
- Theme не меняет смысл цветов, только тональность ролей.
- Glass в light theme остается restraint layer, а не белая дымка поверх всего интерфейса.

## C.4 Material system
| Material | Visual recipe | Primary use | Operational impact |
| --- | --- | --- | --- |
| `Solid Data Surface` | opaque fill, crisp border, low shadow | forms, tables, chat, candidate body, timeline | максимальная читаемость, меньше fatigue |
| `Soft Elevated Surface` | tonal lift, clearer separation, moderate shadow | queue cards, decision cards, contextual summary | помогает группировать решения |
| `Chrome Glass` | translucent tint, restrained blur, sharp edge | top bars, floating search, compact nav, filter bar | отделяет control layer от content without heavy chrome |
| `Overlay Glass` | stronger overlay tint, stronger separation | modal/sheet headers, popovers, lightweight drawers | показывает дополнительный слой поверх текущей сцены |

### Implementation extension: material values
- `Solid Data Surface`: blur `0`, border `1px subtle`, shadow level `1`.
- `Soft Elevated Surface`: blur `0`, border `1px subtle`, shadow level `2`.
- `Chrome Glass`: blur `16-20px`, border `1px subtle`, inner highlight `1px`.
- `Overlay Glass`: blur `20-24px`, border `1px strong`, shadow level `2-3`.

### Glass usage quota
На dense desktop screens glass не должен занимать больше примерно четверти viewport как доминирующий material. Все, что несет длительное чтение или повторяющуюся обработку, должно жить на solid surfaces.

## C.5 Borders, shadows, highlights
- Border default: `1px` semantic border.
- Strong border используется для selected/focus/active group.
- В productive areas не использовать glow и neon-like highlights.
- Shadows: максимум 2-3 уровня.
- Hover state усиливает separation tonal shift и border clarity, а не заставляет блок “подпрыгивать”.

## C.6 Shape, radii, spacing and grid
| Token | Value | Usage |
| --- | --- | --- |
| `radius-12` | `12px` | compact inputs, small buttons, chips |
| `radius-16` | `16px` | primary buttons, filter pills, row actions |
| `radius-20` | `20px` | cards, panels, queue tiles |
| `radius-28` | `28px` | sheets, large overlays, large modals |
| `radius-pill` | `999px` | semantic capsules, segmented toggles |

| Spacing token | Value |
| --- | --- |
| `space-4` | `4px` |
| `space-8` | `8px` |
| `space-12` | `12px` |
| `space-16` | `16px` |
| `space-20` | `20px` |
| `space-24` | `24px` |
| `space-32` | `32px` |
| `space-40` | `40px` |
| `space-48` | `48px` |
| `space-64` | `64px` |

Grid rules:
- Desktop: 12 columns.
- Tablet: 8 columns.
- Mobile: 4 columns.
- Base rhythm: `4px`.
- Main working scale: `8px`.
- Section gap between controls and data: at least `24px`.
- Gap between related controls: `8-12px`.
- Gap between major sections: `32px`.

## C.7 Token naming system
Рекомендуемая модель токенов:
- `reference tokens` для raw values.
- `semantic system tokens` для meaning.
- `component aliases` для конкретных primitives.

### Recommended namespaces
- `--rs-ref-*` для raw palette, spacing, radius.
- `--rs-sys-color-*` для semantic colors.
- `--rs-sys-surface-*` для materials.
- `--rs-sys-text-*` для text roles.
- `--rs-sys-space-*` для spacing.
- `--rs-sys-radius-*` для radii.
- `--rs-sys-motion-*` для durations/easing.
- `--rs-sys-focus-*` для focus.
- `--rs-comp-*` для component-level aliases.

### Examples
```css
--rs-ref-blue-600: #4F7CFF;
--rs-sys-color-accent-primary: var(--rs-ref-blue-600);
--rs-sys-surface-data-solid: #121A2B;
--rs-sys-text-primary: #F6F8FB;
--rs-sys-radius-panel: 20px;
--rs-sys-space-24: 24px;
--rs-sys-motion-duration-filter: 160ms;
--rs-sys-focus-ring-primary: 0 0 0 3px rgba(79, 124, 255, 0.32);
--rs-comp-filterbar-surface: var(--rs-sys-surface-chrome-glass);
--rs-comp-candidate-row-height: 56px;
```

## C.8 Iconography, illustration and empty-state language
- Базовый icon set: `Lucide`, единый stroke weight.
- Размеры: `16` inline, `18-20` toolbar/input, `24` major action.
- По умолчанию иконки монохромны; semantic color только по смыслу.
- Иконка без текста живет внутри icon button с четким hit area.
- Telegram/MAX icons разрешены только как channel markers.

Empty-state language:
- title;
- короткое объяснение;
- одно primary action;
- optional secondary action;
- no dead-end state.

Illustration language:
- не использовать большие декоративные иллюстрации на рабочих поверхностях;
- максимум small symbolic spot illustration для candidate-facing empty/success states;
- recruiter-facing empty states остаются mostly text-first.

## C.9 Focus, hover, pressed, selected, disabled
- Focus ring всегда видим и не заменяется только изменением border-color.
- Hover подчеркивает интерактивность тонально и border-contrast, без лишней scale animation.
- Pressed state: tonal compression, optional micro-scale не ниже `0.985`.
- Selected state должен быть читаем и без hover.
- Disabled state должен отличаться не только opacity, но и недоступностью affordance.

## C.10 Accessibility constraints
- Keyboard navigation обязательна для основных recruiter workflows.
- Label-to-input association обязательна для критичных forms.
- Reduced motion должен сохранять смысл transition, а не просто выключать все.
- Reduce transparency mode должен заменять glass на solid/elevated surfaces.
- TG shell и weak Android devices требуют особой осторожности с blur, shadows и long animated transitions.

## C.11 Operational tables, lists, cards and dense interfaces

### Когда использовать table, list или card
| Pattern | Use when | Do not use when |
| --- | --- | --- |
| Table | много одинаковых объектов, важны сравнение, сортировка, bulk actions | мобильный triage, single dominant CTA, weak metadata |
| List row | нужен быстрый scan + один dominant action + 1-2 lines meta | сложные multi-column comparisons |
| Card | важен state summary, next step, decision framing | когда card начинает скрывать scan speed и превращает data screen в плитку |

### Table rules
- Sticky header обязателен.
- Row height `56px` default, `72px` при secondary line.
- First column: identity plus next action.
- Primary row action state-driven: `Написать`, `Подобрать слот`, `Подтвердить`, а не generic `Открыть`.
- Sticky action column допустима на desktop.
- Bulk actions появляются только после multi-select.
- Density modes: `comfortable` и `compact`; compact доступен только для desktop operators.

### Filtering model
- До data zone не больше пяти primary controls.
- Primary filters в одной строке.
- Advanced filters в sheet/drawer.
- Active filter strip обязателен.
- Saved views важнее, чем десятки постоянно видимых control chips.

### Dark mode scan rules
- Row separators должны быть тише, чем content, но заметнее, чем сейчас в low-contrast glass.
- Small text and timestamps нельзя уводить в декоративную серость.
- Selected row и hover row должны отличаться и в отсутствии pointer hover.

# D. Motion system

## D.1 Motion principles
- Motion показывает причинно-следственную связь.
- Motion удерживает continuity между списком, detail, chat и scheduling.
- Motion локален к объекту и действию.
- Motion никогда не ухудшает scan speed.
- Recruiter should feel continuity, not spectacle.

## D.2 Duration bands
| Scenario | Duration | Pattern |
| --- | --- | --- |
| Hover / focus | `80-120ms` | tonal shift, border emphasis |
| Button press / release | `90-140ms` | tonal compression |
| Filter apply | `140-180ms` | fade + list refresh/reposition |
| Toast / inline success | `160-220ms` | fade / subtle rise |
| List reordering | `160-200ms` | position animation |
| Sheet / drawer open | `180-220ms` | slide + fade + anchored origin |
| Route transition | `220-280ms` | content fade + `8-16px` travel |

## D.3 Easing philosophy
- Standard enter: strong ease-out without bounce.
- Standard exit: short ease-in.
- State transition: neutral ease-in-out.
- No rubber-bounce physics in recruiter operations.

### Implementation extension: easing tokens
```css
--rs-sys-motion-ease-enter: cubic-bezier(0.22, 1, 0.36, 1);
--rs-sys-motion-ease-exit: cubic-bezier(0.4, 0, 1, 1);
--rs-sys-motion-ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
```

## D.4 Pattern-specific transitions

### Route transitions
- List to detail: target content should feel like continuation of selected object.
- Dashboard to filtered candidate list: preserve title context and animate data region, not whole shell.
- Never animate full-screen glass sweeps between admin routes.

### Modal / sheet / drawer
- Drawers should open from the edge or control that triggered them.
- Candidate-side sheets should preserve source anchor and not reset user orientation.
- Close motion mirrors open motion.

### Filters and search
- Search expansion can animate from toolbar icon into field width.
- Applying filters animates data region refresh, not page chrome.
- Active filter removal uses short collapse/fade to confirm change without noise.

### Success, error, loading
- Success feedback appears near the source action and can be mirrored by toast.
- Error feedback anchors to the failing object and preserves recovery path.
- Page loading uses skeletons that match final layout.
- Local action loading stays inside the button/card being acted on.

### Tactile response model
- Button press: tonal compression first, scale optional and minimal.
- Toggle/segmented changes: active capsule glides or fades, not jumps.
- Row hover/selection: low-travel, high-clarity response.

## D.5 Attention guidance patterns
- One-shot coachmark only when first-use confusion is otherwise likely.
- Subtle highlight around newly changed state.
- Brief inline explanation after destructive or consequential mutation.
- Never use permanent help banners to compensate for weak hierarchy.

## D.6 Reduced-motion and low-power behavior
- Replace spatial movement with fade/highlight in reduced-motion mode.
- Replace heavy blur transitions with solid overlays in reduce-transparency mode.
- Telegram and low-end Android modes should prefer immediate, low-cost transitions.

## D.7 Where animation is harmful
- On long data tables.
- On repeated hover states in dense list scanning.
- On message transcript scrolling.
- On auth/loading states where user needs certainty, not spectacle.
- In MAX/TG contexts where platform runtime cost is visible.

# E. Screen-by-screen redesign

_Эта секция является implementation extension of the PRT и опирается на текущие mounted routes, current ownership boundaries и существующий module split._

## `/app/login`
- **Role:** публичный auth entry.
- **Primary task:** быстро и уверенно войти в систему.
- **Current problem:** labels визуально есть, но не semantically bound; error model бедный; form живет внутри glass card и ощущается менее надежно, чем должен; trust/next-step framing слабые.
- **Hierarchy model:** title, trust copy, compact auth form, inline errors, secondary recovery/legacy path.
- **Layout logic:** один центральный solid auth card на quiet background; glass допустим только для outer shell frame, не для field surfaces.
- **Weaken:** декоративность glass, secondary explanatory copy, лишние visual accents.
- **Strengthen:** label clarity, submit CTA, error summary, system trust.
- **Merge:** field errors + submit failure summary в одну понятную grammar.
- **Remove:** placeholder-as-instruction mentality, anonymous loaders.
- **First impression:** secure, compact, calm, purposeful.
- **Next action:** obvious single CTA `Войти`.
- **Required states:** auth check, idle, invalid credentials, network error, submit pending, redirect pending.

## `/app`
- **Role:** shell landing after auth.
- **Primary task:** привести пользователя в рабочий контекст, а не показывать placeholder.
- **Current problem:** current `IndexPage` выглядит как временная заглушка и разрывает flow.
- **Hierarchy model:** redirect-first; optional compact chooser only if last workspace cannot be resolved.
- **Layout logic:** default redirect to `/app/dashboard` or last active workspace; if chooser нужен, это короткий handoff surface.
- **Weaken:** explanatory placeholder copy.
- **Strengthen:** immediate progression into real work.
- **Merge:** landing and context restoration into one bootstrap rule.
- **Remove:** dead-end informational panel.
- **First impression:** system remembers where user should continue.
- **Next action:** automatic; if not possible, offer 2-3 clear workspace entries.
- **Required states:** session restore, role-based redirect, fallback chooser, auth-required.

## `/app/dashboard`
- **Role:** action-oriented overview for recruiter and lead.
- **Primary task:** понять, где нужен первый приоритетный action сегодня.
- **Current problem:** KPI и summary blocks конкурируют с actionability; top area слишком декоративный.
- **Hierarchy model:** context bar, action queues, performance summary, recruiter capacity.
- **Layout logic:** first screen prioritizes `Требуют первого касания`, `Ждут ответа`, `Нужен слот`, `Нужен перенос`, `Overdue`, `Непрочитанные ответы`; KPI остаются вторым слоем.
- **Weaken:** hero-like top panels, decorative KPI competition.
- **Strengthen:** queue cards with counts, risk and single CTA.
- **Merge:** plan-vs-actual and response-time blocks into one performance band.
- **Remove:** visually heavy but non-actionable summary repetition.
- **First impression:** there is work to do, and the system already ranked it.
- **Next action:** each queue card opens prefiltered candidate list.
- **Required states:** zero queue counts, stale data warning, loading skeletons, error per widget, recruiter/admin view variants.

## `/app/candidates`
- **Role:** candidate database and worklist hub.
- **Primary task:** найти нужного человека, увидеть next action и открыть правильный workflow.
- **Current problem:** filter/control overload above the fold; too many chip families; AI block sits too high; row CTA is weaker than metadata.
- **Hierarchy model:** page title + primary CTA + search, one-row primary filters, saved views + view toggle, active filter strip, data view.
- **Layout logic:** primary filters limited to `Stage`, `SLA`, `Channel`, `Recruiter`, `City`; advanced filters move into sheet; list/table default on desktop, card list default on mobile, kanban/calendar stay as secondary views.
- **Weaken:** secondary chip families, equal treatment of all metadata, persistent advanced controls.
- **Strengthen:** first column identity + next action, state-driven row CTA, saved views.
- **Merge:** related filter families into unified filter grammar.
- **Remove:** AI recommendation block from first visual layer; keep as contextual recommendation.
- **First impression:** I can search and filter without fighting the page.
- **Next action:** each row exposes dominant action before “open profile”.
- **Required states:** empty filtered result, auth-required, loading skeleton, bulk-select mode, mobile collapsed cards, stale/out-of-sync warning.

## `/app/candidates/$candidateId`
- **Role:** главный рабочий экран системы.
- **Primary task:** понять текущую ситуацию по кандидату и выполнить следующий шаг без поиска по странице.
- **Current problem:** information richness exists, but first screen is semantically flat; status, next step and actions compete; mobile compression is too high.
- **Hierarchy model:** header triad, conversation-led left column, workflow-led right column, below-fold supporting sections.
- **Layout logic:** 
  - block A: identity + stage + channel + owner;
  - block B: dominant next action card with reason and deadline;
  - block C: action rail `Message`, `Schedule`, `Move Stage`, `Close`;
  - body: left `conversation + activity timeline`, right `workflow stack: stage details, scheduling, notes, evaluation, risks`.
- **Weaken:** competing hero blocks, MAX/TG context as separate visual headline, low-contrast secondary panels.
- **Strengthen:** next action, risk, scheduling state, preferred channel.
- **Merge:** channel health, lifecycle stage and scheduling state into one readable summary model rather than separate competing cards.
- **Remove:** visual equivalence between core action content and supporting info.
- **First impression:** in one glance I know who the candidate is, what stage they are in, what needs to happen now and through which channel.
- **Next action:** one clearly dominant CTA, with secondary actions nearby.
- **Required states:** no channel linked, failed delivery, no slot available, stage blocked, no owner, archived/final outcome, loading skeleton, mobile segmented view.

## `/app/slots`
- **Role:** scheduling and capacity workspace.
- **Primary task:** быстро найти availability, подобрать слот и решить reschedule.
- **Current problem:** too many controls before results; progressive disclosure weak; likely overload across desktop and mobile.
- **Hierarchy model:** context bar, primary filters, two core modes, data/result area, local problem-solving states.
- **Layout logic:** 
  - primary filters `City`, `Recruiter`, `Date Range`, `Status`;
  - modes `Availability Board` and `Request Queue`;
  - advanced filters in sheet;
  - result area emphasizes usable slots and blocked/problem states.
- **Weaken:** raw admin-form appearance of filters.
- **Strengthen:** scheduling outcome, next available slot, alternate suggestion.
- **Merge:** request-related states into dedicated request queue instead of scattering them.
- **Remove:** dead-end empty states.
- **First impression:** this is a scheduling tool, not a filter form.
- **Next action:** select slot, request alternate, or waitlist/handoff from the same scene.
- **Required states:** no slots, no recruiters, no cities, reschedule requested, waitlist/manual availability, booking success, booking conflict, mobile condensed mode.

## `/app/recruiters`
- **Role:** recruiter roster and capacity management.
- **Primary task:** увидеть, кто перегружен, кто свободен и куда можно перекинуть поток.
- **Current problem:** decorative card treatment weakens operational scan speed.
- **Hierarchy model:** compact roster first, optional grid as secondary mode.
- **Layout logic:** each row/card shows recruiter, city/timezone, local time, load today, next free slot, open tasks and one quick action.
- **Weaken:** profile-gallery feeling, decorative card chrome.
- **Strengthen:** load indicators, local time, quick assign/open schedule.
- **Merge:** availability and load into one compact summary line.
- **Remove:** visually heavy profile cards as default.
- **First impression:** I can rebalance work, not browse people.
- **Next action:** open schedule or assign candidate directly.
- **Required states:** empty roster, unavailable recruiter, timezone mismatch, mobile stacked list, loading/error.

## `/tg-app`
- **Role:** Telegram quick triage shell.
- **Primary task:** дать рекрутеру one-handed entry into urgent work.
- **Current problem:** inline-style chaos, weak shared semantics, visual and behavioral gap from SPA.
- **Hierarchy model:** compact header counters, queue cards, incoming list.
- **Layout logic:** 2-3 counters (`New`, `Reply Due`, `Today Interviews`), then compact queue cards, then incoming items; native-like solid panels using Telegram theme params.
- **Weaken:** custom styling noise and non-semantic color usage.
- **Strengthen:** urgency visibility, CTA clarity, thumb-first layout.
- **Merge:** counter cards and queue entry points into one triage-first top area.
- **Remove:** heavy backdrops and glass-heavy patterns.
- **First impression:** quick, clear, respectful of Telegram environment.
- **Next action:** one tap into the highest-priority queue.
- **Required states:** no initData, loading, empty queues, network error, safe-area handling, low-end performance mode.

## `/tg-app/incoming`
- **Role:** incoming triage list inside Telegram.
- **Primary task:** за секунды понять, кого брать первым и что делать.
- **Current problem:** flat cards, compressed meta line, urgency and next best action not visible enough.
- **Hierarchy model:** identity, stage/urgency, wait signal, channel/city meta, one primary CTA, secondary expand.
- **Layout logic:** each card: name, stage, urgency badge, waiting time / last message, city, channel, primary CTA and optional expand.
- **Weaken:** generic “open card” posture.
- **Strengthen:** urgency, waiting time, next action, status consequence.
- **Merge:** waiting time and reply-due signal into one stronger operational cue.
- **Remove:** decode-heavy thin text rows.
- **First impression:** triage order is obvious.
- **Next action:** reply, schedule or open candidate summary.
- **Required states:** empty list, retry error, loading, safe area, very long names, overdue highlight.

## `/tg-app/candidates/$candidateId`
- **Role:** lightweight candidate action surface inside Telegram.
- **Primary task:** быстро посмотреть контекст и выполнить 1-2 mutations.
- **Current problem:** current screen is too thin on context and too close to raw admin actions.
- **Hierarchy model:** summary card, next action card, conversation excerpt, compact action group.
- **Layout logic:** top summary = stage, urgency, channel, owner; then next action with reason; then last conversation excerpt; then action group `Reply`, `Schedule`, `Move Stage`.
- **Weaken:** unstructured status mutation button list.
- **Strengthen:** state explanation and consequence copy.
- **Merge:** status and context into one readable summary instead of separate thin blocks.
- **Remove:** assumption that Telegram screen should reproduce full SPA detail.
- **First impression:** this is a quick decision screen, not a reduced admin form.
- **Next action:** at most two sticky primary actions on mobile.
- **Required states:** missing channel, action pending, mutation success/error, long thread preview, safe-area sticky bar.

## `/miniapp`
- **Role:** bounded candidate-facing journey for test, booking and follow-up.
- **Primary task:** всегда объяснять текущий статус, следующий шаг и fallback.
- **Current problem:** candidate-first rhythm is already strong, but tokens/semantics still feel visually detached from the rest of the product and some dark cards are too layered.
- **Hierarchy model:** current state, next step, support/fallback.
- **Layout logic:** one mounted route with state clusters, not multiple fake routes; every state card follows one grammar: title, explanation, primary CTA, secondary fallback.
- **Weaken:** unnecessary multi-layer dark treatments and CRM-like jargon.
- **Strengthen:** progress clarity, reassurance, next-step framing, human language.
- **Merge:** no-slot/manual-review/contact-required states into one card grammar with different semantic tone.
- **Remove:** internal HR status names from candidate-facing copy.
- **First impression:** calm, understandable, resumable flow.
- **Next action:** always visible and human-readable.
- **Required state clusters:** bootstrap/intake, home/status, test in progress, booking selection, manual availability, booking success, no slots/no cities/no recruiters, contact required, manual review, chat ready/help.

# F. Core workflow redesign

## F.1 Candidates list

### Information architecture
- Top bar: page title, `New Candidate`, state-aware search.
- Primary filter bar: `Stage`, `SLA`, `Channel`, `Recruiter`, `City`.
- Saved views and view switcher on the same horizontal level.
- Active filter strip below primary controls.
- Data zone as default table/list; kanban/calendar remain alternate modes.
- Selection bar appears only after multi-select.

### Visual hierarchy
- First scan target: candidate identity and dominant next action.
- Second scan target: stage and urgency.
- Third scan target: channel, owner, last touch, city.
- AI recommendation is contextual and subordinate to human workflow controls.

### Primary CTA
- Global: `New Candidate`.
- Row-level: state-driven action tied to candidate condition.

### Secondary CTA
- Open full profile.
- Add to selection.
- View alternate mode.

### Above-the-fold rule
Above the fold must show:
- title;
- search;
- at most five primary controls;
- saved views;
- active filter strip if filters exist;
- first data rows/cards.

It must not show:
- multiple competing chip families;
- heavy AI blocks;
- bulky advanced filters;
- explanatory chrome that pushes data below fold.

### Progressive disclosure
- Advanced filters move into sheet/drawer.
- Rare metadata hides behind expand, hover detail or row secondary line.
- Bulk actions appear only after explicit selection.

### State model
- Default worklist.
- Filtered result.
- Empty base state.
- Empty filtered state.
- Bulk-select mode.
- Loading skeleton.
- Auth-required.
- Recoverable error.

### How to reduce noise
- Collapse metadata into fixed secondary zones.
- Use one badge grammar instead of multiple chip styles.
- Use icon sparingly and only when it accelerates scan.
- Move explanation text into empty states, helper rows and hover details, not into every row.

### How to improve scan speed
- Stable column order: identity, next action/urgency, stage, channel, owner, last touch.
- Stronger CTA than metadata.
- Sticky header and optional sticky action column.
- Tabular numerals for SLA and time fields.

### How to reduce recruiter fatigue
- Fewer always-visible controls.
- Predictable row grammar across views.
- Saved views for repeated daily tasks.
- Less color competition across badges.

### Mobile behavior
- Default to card list, not dense table.
- Keep one dominant CTA per card.
- Secondary metadata collapses to two lines.
- Filter sheet replaces horizontal chip overflow.

## F.2 Candidate detail workspace

### Strategic role
Candidate detail must become the heart of RecruitSmart. It is the place where identity, conversation, scheduling, stage movement and risk resolution become one scene.

### Always-visible top summary
Above the fold, without scrolling, user must always see:
- candidate identity;
- current stage;
- current urgency;
- dominant next action;
- preferred channel;
- owner;
- key risk/blockers.

### Information architecture
- Header triad.
- Left column: conversation and activity timeline.
- Right column: workflow stack.
- Below fold: supporting info, tests, AI, historical detail, archival context.

### Header triad
| Block | Content | Purpose |
| --- | --- | --- |
| Identity block | name, city, stage, channel, owner | establish object and current state |
| Next action block | dominant task, reason, deadline, consequence | tell operator what matters now |
| Action rail | Message, Schedule, Move Stage, Close | give immediate execution path |

### Primary CTA
Dynamic and state-driven:
- `Написать кандидату`
- `Подобрать слот`
- `Подтвердить интервью`
- `Запросить данные`
- `Закрыть кейс`

### Secondary CTA
- Open script.
- View AI suggestion.
- Expand history.
- Open channel health details.

### Progressive disclosure
- Supporting info goes below fold or into collapsible sections.
- AI remains advisory and never outranks primary operational state.
- MAX/TG context appears as info panel, not as hero block.
- Rare admin metadata collapses.

### State model
- Normal active workflow.
- Awaiting reply.
- No linked channel.
- Delivery failed.
- Slot missing.
- Reschedule requested.
- Manual review or blocked state.
- Final outcome / archived.

### How to reduce noise
- Separate stage, urgency, risk, channel and owner into distinct semantic patterns.
- Reduce card count in first screen.
- Collapse low-value meta and duplicated summaries.
- Keep timeline and conversation visually related but not identical.

### How to improve scan speed
- Large next action card with reason.
- Limited number of primary actions.
- Strong contrast between core summary and supporting panels.
- Timeline events and system events share consistent grammar.

### How to reduce recruiter fatigue
- Fewer context switches.
- Messaging and scheduling live inside the same mental frame.
- Supporting information reveals on demand.
- Channel problems are specific, not buried in generic alerts.

### Mobile behavior
- Four segments: `Summary`, `Chat`, `Schedule`, `History`.
- Sticky bottom action bar with at most two primary actions.
- Summary segment always includes identity, stage, urgency, next action, owner.
- Avoid trying to compress full desktop detail into one vertical stack.

## F.3 Integrated messenger / communication experience

### Current runtime truth
Today communication is split between:
- standalone `/app/messenger` workspace with thread list and thread view;
- `CandidateChatDrawer` inside candidate detail.

This is a valid architecture base, but it needs one visual and interaction grammar.

### Target model
Keep two entry modes, one message system:
- `/app/messenger` = cross-candidate inbox and queue handling.
- Candidate detail conversation = candidate-centric execution inside workspace.

### Shared message primitives
- `MessageThreadList`
- `MessageHeader`
- `MessageGroup`
- `MessageBubble`
- `SystemEventRow`
- `DeliveryStatusPill`
- `QuickReplyTray`
- `TemplatePicker`
- `Composer`
- `CandidateContextPane`

### Information architecture
- Inbox route: list on left, thread in center, optional candidate context on right.
- Candidate detail: conversation is main left column section, context already exists in header/right rail.
- On mobile: thread list and thread view are separate navigable states.

### Candidate context next to dialogue
Conversation must show:
- current stage;
- urgency;
- preferred channel;
- next action;
- owner;
- booking status if relevant.

Context must be glanceable, not full duplicate of candidate detail.

### Current status without overload
- Use a small semantic summary strip near thread header.
- Do not repeat full candidate hero inside messenger.
- Delivery problems surface inline near latest relevant outbound message and in thread header.

### Templates / quick replies / escalation
- Templates are not separate UX universe; they are part of composer workflow.
- Quick replies should be state-aware and context-bound.
- Escalation actions should stay adjacent to relevant conversation state: `Открыть профиль`, `Подобрать слот`, `Передать вручную`.

### Message grammar
| Type | Visual treatment | Why |
| --- | --- | --- |
| Inbound human | neutral solid bubble | core incoming content |
| Outbound human | accent/tonal bubble | clearly operator action |
| Automated/system | system event row, not normal bubble | avoid confusing machine and human messages |
| AI draft | composer-side suggestion card | advisory, not sent state |
| Delivery issue | inline status pill + local explanation | actionable failure, not generic banner |

### What must be above the fold
- Thread identity.
- Candidate context strip.
- Last meaningful messages.
- Composer or explicit reason why messaging is unavailable.

### How to reduce noise
- Separate transcript from system history.
- Hide low-value meta under hover/expand or secondary timestamp line.
- Keep template tray contextual and collapsible.

### Mobile behavior
- Sticky composer.
- At most one expanded context block.
- Thread header remains compact and actionable.
- Avoid three-column logic on small screens.

# G. Unified semantic language

## G.1 Semantic contract
| Entity | Recruiter-facing meaning | Candidate-facing translation | Visual grammar | SPA / TG / MAX adaptation |
| --- | --- | --- | --- | --- |
| Stage | Где кандидат находится в процессе | “На каком шаге вы сейчас” | neutral/accent stage badge | Same meaning everywhere; MAX uses translated human label |
| Urgency | Насколько срочно нужен action | usually hidden unless relevant to candidate | semantic urgency badge with time cue | TG and SPA show explicit urgency; MAX uses gentle time framing only when useful |
| Risk | Вероятность потери или блокера | human explanation only if candidate must know | warning/danger risk badge or risk card | MAX avoids internal risk jargon |
| Channel | Через что можно продолжить | where service will contact candidate | outline/tonal channel badge with icon | Channel colors never own the page |
| Owner | Кто отвечает за кейс | usually not surfaced to candidate | neutral owner badge/meta label | Visible in SPA/TG, mostly hidden in MAX |
| Next action | Что надо сделать сейчас | what you should do next | decision card / dominant CTA | Must exist on every key surface |
| Empty | Нет объектов или нет результата | нет доступного шага, но есть fallback | title + explanation + primary action | Same grammar, different tone |
| Loading | Проверяем/загружаем | same | skeleton or explicit auth check | Differentiate auth, page, local action |
| Error | Что сломалось и что делать дальше | plain-language problem + fallback | inline error card anchored to object | No raw server copy |
| Success | Что выполнено и что будет дальше | explicit confirmation | inline/local success + optional toast | Always tied to object and next state |
| Warning | Есть ограничение или нужен ответ | gentle caution if candidate-relevant | tonal warning badge/card | Used sparingly; not same as risk |
| Messaging marker | reply due, handoff, delivered, failed | candidate sees only meaningful communication state | thread markers and pills | Shared grammar across messenger and detail |

## G.2 Stage presentation rules
- Не invent new backend stages inside design layer.
- Use existing lifecycle states, but normalize display into consistent presentation groups.
- Recommended display grouping for UI:
  - `Intake`
  - `Screening`
  - `Test`
  - `Scheduling`
  - `Interview / confirmed`
  - `Outcome`

UI grouping не меняет backend status model; это display normalization.

## G.3 Urgency model
- `On track`
- `Reply due`
- `Overdue`
- `Blocked`

Presentation rules:
- urgency never replaces stage;
- urgency is about timing and required action;
- urgency gets icon/time cue;
- candidate-facing MAX uses plain-language phrasing instead of internal urgency badge when needed.

## G.4 Risk model
- `Low attention`
- `Needs attention`
- `High risk`
- `Critical block`

Risk is distinct from urgency:
- urgency asks “когда действовать”;
- risk asks “что можно потерять”.

## G.5 Channel model
- `Telegram`
- `MAX`
- `Phone`
- `No linked channel`

Rules:
- show as compact channel badge with icon;
- delivery state is separate from channel identity;
- preferred channel can be highlighted in candidate detail and messenger.

## G.6 Next action grammar
Next action copy format:
- verb;
- object;
- optional time constraint;
- optional reason.

Examples:
- `Написать кандидату до 14:00`
- `Подобрать слот на сегодня`
- `Подтвердить интервью`
- `Запросить номер для связи`

Candidate-facing translations should be human:
- `Выберите удобное время`
- `Мы проверяем анкету`
- `Нужен ваш номер для связи`

## G.7 Loading, empty, success, error and warning states
- `Auth check`: explicit branded check screen with clear outcome.
- `Page loading`: skeleton of actual screen.
- `Local action loading`: only the active control blocks.
- `Empty state`: clear reason + primary action + optional secondary action.
- `Error state`: problem, what is still available, what to do next.
- `Success state`: result + next expected system behavior.
- `Warning state`: constraint or upcoming deadline, not failure.

## G.8 Messaging / handoff / follow-up markers
- `Awaiting reply`
- `New inbound unread`
- `Delivery failed`
- `Handoff sent`
- `Follow-up due`
- `No channel linked`
- `Manual review required`

These markers must be readable in:
- thread list;
- thread header;
- candidate detail summary;
- TG candidate card;
- MAX fallback/help cards when candidate context makes it relevant.

# H. 24-hour implementation plan

## H.1 Priority backlog

### P0
- Explicit auth-required state for protected routes instead of indefinite loader.
- Login screen label association, inline errors and submit-state cleanup.
- Candidates page split into primary filters + advanced filters.
- State-driven primary row CTA in candidates list.
- Candidate detail header rebuilt into identity + next action + action rail.
- Contrast uplift for chips, timestamps and small text in dark mode.
- Unified empty/loading/error patterns for main recruiter surfaces.

### P1
- Dashboard redesign toward action queues first.
- Unified semantic badge grammar.
- Candidate detail messaging-first body layout.
- Slots request queue and no-dead-end scheduling states.
- Telegram shell alignment with shared semantics and stronger triage cards.
- Mobile segmentation on candidate detail.

### P2
- Shared component layer for `/app`, `/tg-app` and `/miniapp` adapters.
- Unified semantic token rollout.
- Shared messaging primitives across inbox and candidate detail.
- Motion/accessibility modes including reduce-transparency.
- Potential dedicated inbox refinements after core workflow stabilizes.

## H.2 First 24 hours: safe changes with highest UX effect
- Add explicit auth-required screen and deterministic auth bootstrap outcome.
- Fix `/app/login` semantics, errors and trust layout.
- Reduce above-the-fold filter noise on `/app/candidates`.
- Make candidates row CTA visibly stronger than metadata.
- Rebuild candidate detail top area into header triad.
- Raise contrast on badges and small text.
- Standardize empty/loading/error/auth states across `/app/dashboard`, `/app/candidates`, `/app/candidates/$candidateId`, `/app/slots`.

## H.3 Low / medium / high-risk classification
| Change | Risk | Reason |
| --- | --- | --- |
| Auth-required state | Medium | touches protected-route experience but not business logic |
| Login semantics and copy | Low | mostly UI and accessibility |
| Candidate filter hierarchy | Low | UI-only if query model unchanged |
| Row CTA strengthening | Low | presentation and CTA ordering |
| Candidate detail header triad | Medium | touches critical workspace composition |
| Badge grammar | Low/Medium | widespread visual semantics change |
| Dashboard action queues | Medium | changes primary screen hierarchy |
| Slots request queue | Medium | scheduling UX changes without backend contract change |
| TG shell alignment | Medium | separate runtime constraints |
| Shared component layer rollout | High | cross-shell refactor surface |

## H.4 Что сначала отдать в дизайн
- Semantic foundation: typography, color roles, materials, badge grammar.
- Redlines for auth states, candidates filter bar, candidate row, candidate header triad.
- Screen-level specs for dashboard queues, slots request queue and TG triage cards.
- Candidate-facing copy/state cards for `/miniapp`.

## H.5 Что можно сразу отдавать во frontend
- Auth-required state.
- Login accessibility fixes.
- Primary filter bar + advanced filter sheet.
- Active filter strip.
- Semantic badge component set.
- Candidate row state-driven CTA.
- Candidate detail header triad skeleton.
- Unified empty/loading/error/auth components.

## H.6 Shared primitives to build first
- `AuthRequiredState`
- `PrimaryFilterBar`
- `AdvancedFilterSheet`
- `ActiveFilterStrip`
- `QueueCard`
- `DecisionCard`
- `CandidateRow`
- `CandidateHeaderTriad`
- `SemanticBadgeSet`
- `MessageEventRow`
- `StickyMobileActionBar`

## H.7 Screens to redesign first for maximum UX effect
1. `/app/candidates`
2. `/app/candidates/$candidateId`
3. `/app/login`
4. `/app/dashboard`
5. `/app/slots`
6. `/tg-app/incoming`
7. `/tg-app/candidates/$candidateId`
8. `/miniapp` state cards and semantics

## H.8 Safe rollout strategy
- Start with semantic and hierarchy changes that do not touch backend contracts.
- Keep route ownership stable: candidates logic stays in candidates module, messenger logic stays in messenger module, shell logic stays in `__root.tsx`.
- Roll out new shared primitives before route-specific polish where possible.
- Avoid cross-shell refactor until semantics and top-priority screens are proven.

# I. Design QA checklist

## I.1 Consistency
- One semantic badge grammar across `/app`, `/tg-app`, `/miniapp`.
- Same meaning for stage, urgency, risk, channel and next action on all surfaces.
- One typography hierarchy across shells, with allowed platform fallback only.
- Candidate-facing copy never leaks internal recruiter jargon.

## I.2 Hierarchy
- Every recruiter-facing screen has one dominant next action.
- Above the fold in candidates does not exceed five primary controls before data.
- Candidate detail shows identity, stage, urgency, next action, channel and owner on first screen.
- Dashboard queues outrank secondary KPI.

## I.3 Contrast and readability
- Small text and timestamps remain readable in dark mode.
- Glass never reduces readability in data zones.
- Status pills, selection states and focus states pass contrast targets.
- Candidate-facing MAX cards remain readable under platform theme constraints.

## I.4 Motion
- Motion explains origin/result and never feels decorative.
- Route transitions preserve continuity between related objects.
- Reduced-motion mode keeps meaning via fade/highlight replacements.
- TG/MAX environments do not carry heavy blur or expensive transitions.

## I.5 Accessibility
- Login labels are semantically associated with inputs.
- Keyboard and focus behavior works on core desktop workflows.
- Auth, loading, success and error states are distinguishable.
- Reduce-transparency mode has a solid-surface fallback.

## I.6 State coverage
- Protected routes never hang in endless loader.
- Every key screen has loading, empty, error and success patterns.
- `/miniapp` covers no slots, no cities, no recruiters, contact required, manual review and chat-ready.
- TG screens handle missing `initData`, loading and network error clearly.

## I.7 Mobile adaptation
- Candidate detail has segmented mobile behavior, not compressed desktop stacking.
- TG screens respect safe area, tap target size and thumb zones.
- Mobile filter interaction uses sheets instead of overflowing control rows.
- Sticky bottom action bars never exceed two primary actions.

## I.8 Recruiter efficiency
- Row CTA is faster to scan than secondary metadata.
- Saved views reduce repeated filter work.
- Queue cards open meaningful prefiltered worklists.
- Messaging, scheduling and stage change can happen without context loss.

## I.9 Candidate clarity
- MAX states explain current step, next step and fallback.
- Booking success confirms time, channel and what happens next.
- Manual review is explained in human language.
- No candidate-facing state ends in a dead end.

## I.10 Semantic consistency across Telegram / MAX / SPA
- Same state has the same name or the same translated meaning everywhere.
- Telegram and MAX adapt to platform shell, but do not invent separate semantics.
- Channel identity is visible without brand takeover of the page.
- Handoff, reply due, manual review and booking states are consistently named and visually distinguished.

### PRD gaps, contradictions, and risks
- **Vocabulary contract is not fully productized yet.** PRT requires one vocabulary everywhere, but stage aliases, next-action labels, close reasons and candidate-facing translations still need explicit product approval as a canonical contract.
- **Typography rollout needs a platform decision.** PRT recommends `Inter Variable`, while current SPA uses `Manrope`/`Space Grotesk` and TG/MAX may need `system-ui` for performance. Team must approve exact fallback behavior before implementation.
- **Messenger ownership needs rollout discipline.** Current runtime has both `/app/messenger` and `CandidateChatDrawer`. Redesign should unify grammar first, not prematurely merge modules or reroute business logic.
- **Saved views need scope control.** UX strongly benefits from saved views, but server-persisted views would expand scope. Safe first step is local persisted views; backend persistence should be a separate task.
- **Stage grouping must stay display-only.** Proposed display groups improve clarity, but they must not silently replace backend status semantics or reporting semantics.
- **MAX semantics must remain bounded.** PRT points toward a coherent MAX experience, but current runtime is still bounded pilot only. The redesign must not imply full MAX production availability or unsupported flows.
- **Telegram shell has stronger performance constraints than SPA.** Shared semantics are required, but shared rendering should stay adapter-based. Reusing meaning does not justify reusing heavy visual patterns.
- **Candidate detail can become overloaded again if every subsystem fights for the header.** The triad only works if AI, channel health, MAX context and risk remain subordinate to stage and next action.
- **Auth and protected-route behavior is a visible must-fix.** Current loader-like bootstrap ambiguity directly contradicts the PRT quality bar and should be treated as first-line UX debt.
