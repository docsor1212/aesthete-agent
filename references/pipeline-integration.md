# 既有封面/课件流水线的接入点(2026-10-15 实战验收通过)

原则:**锁定风格不动**。iei-cover(bees_honey)与 glm-deck(黄蓝斜纹)是已验收的品牌系统,palette-forge 只在"新变体/新品牌"场景供给配色;接入方式永远是**复制脚本改副本**,原件零改动(本文件所记两条链路已各跑通一次端到端验收)。

## iei-cover(H3 封面管线)接入点

管线:`底图+文字卡(H3) → compose_ep.py(PIL 合成/chip/药丸/横幅) → qc_covers.py OCR 质检`。

颜色注入面(compose_ep.py 内 5 处常量,已定位行号以 2026-10 版本为准):

| 元素 | 原色(bees_honey) | 注入点 |
|---|---|---|
| chip1 边框/字(系列身份) | 珊瑚 ffa69e / E07066 | `CORAL_BORDER/CORAL_TEXT`(L17)——**系列芯片保留**,不接 |
| chip2 边框/字(指南胶囊) | 雾蓝 aed9e0 / 石板 | `MIST_BORDER/MIST_TEXT`(L18) |
| 药丸 底/边(病名标本) | 珊瑚 | `make_pill` 默认参 fill/border(L108) |
| 横幅 底(副题) | 石板 5e6472 | `make_banner` 默认参 fill(L143) |
| 白带渐变(标题带) | faf7ee→faf3dd | `repaint_band` 的 top_c/bot_c(约 L175-176) |

标准流程(H3 不可用时验证过):
1. 六步法第 1 步先写约束:**文字卡字色(珊瑚)是 H3 资产锁定的绑定约束**,新配色围绕它做互补/协调(The brief wins)。
2. `harmony --base ffa69e --mode complementary` 等得到方案;`score` 过 ≥14 分。
3. `cp compose_ep.py pf_test/compose_pf.py` 后只改上表 4 处(chip1 保留);qc_covers.py 一并复制。
4. 跑合成(SKILL v33 默认坐标)+ `qc_covers.py --ep 0N` OCR 必含清单 + emitImage 目检。

验收记录(2026-10-15):EP02 底图 `scidv19_base02_1_00001_.png`+文字卡 `scidv18_card02_1_00001_.png`,"珊瑚×深青"变体(harmony 互补:药丸 06818B/横幅 1D4E5F/白带 FDF9F5→FEF6EC/chip2 青边)→ 合成成功,OCR 1/1 PASS,目检协调。产物 `h3_cover_repro/pf_test/iei02_pf_variant.png`。已知边界:布局坐标沿用 SKILL 文档默认,底图为早期代次资产时药丸右缘可能与道具轻微叠压——生产线按 SKILL 双向解约束重调,不属配色集成问题。

## glm-deck(黄蓝斜纹课件)接入点

管线:`deck.html 模板 + style-tokens.css(唯一颜色事实源) → build.py 单文件构建 → judge/截图验收`。

颜色注入面 = style-tokens.css 的 `:root` 十个变量,令牌映射表:

| glm-deck 变量 | 语义 | palette-forge 角色 |
|---|---|---|
| `--paper` | 页底 | bg(建议向白提亮一档保投影通透) |
| `--ink` / `--ink-2` | 正文/次级 | text / text 提亮档 |
| `--blue` `--blue-deep` `--blue-ink` `--blue-wash` | **证据·检查**(冷相) | primary 及其深浅档(色相任取,保持"冷=证据") |
| `--yellow` `--yellow-deep` `--yellow-wash` | **决策·危险**(暖相) | accent 及其深浅档(保持"暖=决策") |
| `--line` | 细线 | surface 族浅档 |

标准流程:`cp <skill>/assets/style-tokens.css <项目>/` 改副本 `:root` → 模板 `<link>` 指向副本 → build.py 正常构建。**semantic 映射必须保序**(铁律 5):证据用冷相角色、决策用暖相角色,只换色相不换语义方向,否则 judge 按"反语义"判不合格。

验收记录(2026-10-15):库板 Warm Autumn Glow(003049/F77F00 系,★★ 48.1K)→ 3 页测试 deck(封面+flow 内容页+hbars 图表页)→ build.py 自检 OK → 三页截图目检全过:装饰八件套自动换色、字号铁律由令牌保证、蓝/黄语义同构保持。产物 `h3_cover_repro/pf_test/glm_deck_test/`。

⚠️ **交付坑(实测踩过)**:build.py 产物**不是自包含单文件**——内核与图片会内嵌,但 `style-tokens.css` 仍是 `<link>` 外链。本地 HTTP 预览正常,一旦单独把 HTML 发给别人(飞书传文件),对方打开就是全空白页。**发文件前必须内联 CSS**:把 `<link rel="stylesheet" href="style-tokens.css">` 替换为 `<style>`+css 全文,再 grep 确认无真实外链(内核注释里的 `src="deck-stage.js"` 字样属文档注释,无害)。

## 禁区提醒

- 不修改 iei-cover / glm-deck 的 SKILL.md、脚本与令牌原件(改前必备份,改副本);本 skill 与二者的协作是**单向供弹**。
- 系列已发布封面的 bees_honey、glm-deck 已验收黄蓝,不属于 palette-forge 的改配对象(用户审美铁律:已验收设计=禁区)。
