---
version: 0.6.0
name: aesthete-agent
description: 配色生成、调色板方案、前端美学:为 UI/HTML、SVG 幻灯片、视频封面、图表、海报输出机械验证过的颜色方案。87 板实证库按语域自动匹配,OKLCH 谐和生成、明度阶梯、图像取色;60-30-10 角色化含语义色;五维评分卡、WCAG 对比度、色盲模拟、AI-slop 检测四重机械验证;card 上下文预览+六场景 visualizer+五镜自审;偏好学习档案随你的每次裁决进化。内置命名主题包、全对对比度矩阵、色盲安全数据色、五镜报告生成器与 APCA(WCAG 3 草案)感知对比度。纯标准库离线可用。Skip when:纯文字排版、翻译润色、文案写作、与配色和前端美学无关的任务。Aesthete Agent。触发词:配色、调色板、配色方案、颜色搭配、前端美学、UI配色、设计美学、color palette、color scheme、WCAG、色盲、视觉审美、visualizer、aesthete-agent。
---

# aesthete-agent — 前端美学引擎

大模型配色差的根因:模型把 hex 当文本操作、输出训练数据中位数(前端教程的中位数是紫/靛蓝)、无法真正"看见"颜色。修法不是换模型,而是**把品味外包给流程**:哲学先行、角色化、机械验证、上下文自审。

⛔ 铁律:
1. **禁止裸写配色**。任何设计任务的配色必须走六步法,第 6 步(五镜自审)不可跳过。
2. **禁止运行时访问 the source site**——无公开 API,直连被 Cloudflare 403;数据已离线内置。
3. **Brief 即法律**:用户/上游指定的颜色与美学方向是绑定约束,本 skill 围绕它服务。已有品牌色系的既有交付不属本 skill 改配对象。
4. **有界验证**:完整做完→一轮批量自审→一轮批量修复→最多再确认一次→**停止打磨**。
5. **候选纪律**:送用户裁决必须 ≥2 个整页候选(`make_variants.py` 合成对比页);单方案不得送审。
6. **裁决回写**:用户每次接受/否决,落 `profile.json`(机读)与 `critique.md` 尸检(失败模式)——不回写 = skill 不长。

## 能力×边界速查

| 能力 | 做到 | 不做到 | 深入 |
|---|---|---|---|
| 选库 match/search | 按语域+点赞分层+客观门从 87 板实证库排序 | 不判"主观好看"——最终裁决在上下文自审 | curation.md |
| 生成 harmony / ramp / mutate | OKLCH 谐和/明度阶梯/感知等量变换,自动 gamut 收缩 | 不做插图/渐变图导出 | color-theory.md |
| 取色 extract | 从参考图提取主色+占比+文字色建议 | 不做图像重绘/抠图 | — |
| 角色 roles | bg/text/accent/primary/surface+语义色,附对比度检查 | 不替代排版系统与字体选型 | craft-rules.md |
| 验证 score/contrast/blind | 五维评分卡、WCAG 边界值、色盲三模拟,失败给修复建议 | 不判审美;对比度是必要非充分条件 | color-theory.md |
| 主题 themes/theme | 8 个命名主题包(配色+字体+语气+适用域),一键输出 CSS token 集 | 不生成图像资产 | palettes/themes.json |
| 矩阵 matrix | 全对对比度矩阵 + 最优配对推荐,支持 APCA(WCAG 3 草案感知算法) | APCA 指南仍为草案 | — |
| 数据色 semantic | 色盲安全分类色(明度阶梯+色相均布,内置去盲验证) | 不做热图连续渐变(用 ramp) | — |
| 报告 critique | 五镜报告生成器:机械发现预填,guided 表单+finding ledger | taste 裁决仍需 agent/人 | critique.md |
| 体检 doctor | 部署健康一键诊断(库/主题/档案/工具/引擎) | — | — |
| 反模式 slop + lint_page | 中位数陷阱/紫渐变/平坦明度检出;HTML 交付审计——**任何渐变(线性/径向/锥形)即 P0 不合格: 一律纯色分层** | 不覆盖所有审美失败模式——五镜截图补位 | anti-slop.md |
| 验收 report | 一键 `report` 把对比度/色盲/AI-slop/评分四闸聚合成单一 PASS/FAIL JSON(退出码=裁决),直通裁决回写 | 不替代审美判断——五镜截图仍必做 | critique.md |
| 预览 card / showcase / make_variants | 色板卡+mockup;样张点名;≥2 候选对比页 | 不替代真实环境冒烟测试 | critique.md |
| Visualizer 场景+变体+SVG 重着色 | 10 类真实场景(手机应用/落地页/仪表盘/品牌/字阶/图案/数据图表/商品卡/邮件/编辑页),角色派生+可读性闸门+文字阶梯;--variants N 同场景×N 次色板排列;SVG 槽位清单重着色(按设计自身颜色秩映射,纯黑白保留),--shuffle N 出多排列对比网格 | 场景样张是决策辅助,不是生产 UI | critique.md |
| 学习 house + profile.json | 已验收设计入库;偏好(深浅/黑名单/语域)机读生效 | 学习档案即配置文件,改法见"裁决回写"节 | curation.md |

**非目标**:排版系统、图像资产生成、印刷 CMYK 色域、字体选型——本 skill 只管颜色决策与验证。

## 六步法

命令变量(先设一次):`SDIR="<本 skill 目录绝对路径>"`,`S="$SDIR/scripts/palette_forge.py"`。

### 第 1 步:命名美学宣言

起一个 **1-2 词的运动名** + 一句话宣言:"药圃手账——陶罐褐、晒干草本绿、桑皮纸米黄,低饱和,像被时间晒过"。宣言包含:
- **语域判定**(镜 0):给谁看/什么场景看/3 秒带走什么;视觉语域与内容领域同域。**用户既有审美档案(如素雅/浅底/留白/大幽灵数字)是最高优先约束,先查再写;隐喻契合救不了语域错配**;
- **参照美学**:"1970s 滑雪小屋:焦橙、牛油果绿、暖棕";
- **明暗架构**:浅底还是深底;文字永远最深/最浅;
- **色彩剂量**:点缀色全页占比 ≤10%,"稀缺即力量";
- **否定清单**:从 `references/anti-slop.md` 挑适用项写进 prompt(推理期否定有效);
- 60-30-10 是**默认脚手架,不是法律**——比例追随 brief。

### 第 2 步:选来源(四条路)

```bash
python "$S" match --brief "儿科临床教学页" --limit 6     # A' brief匹配:自动判语域+档案降权(首选)
python "$S" search --style warm,pastel --no-flags --limit 6   # A 手动过滤
python "$S" harmony --base 780000 --mode complementary --theme light  # B OKLCH 谐和
python "$S" extract reference.png --n 6                  # C 图像取色(需 Pillow)
python "$S" ramp --base 2A9D8F --steps 7                 # D 明度阶梯(图表/热图)
```

A'=自然语言 brief → 语域判定+档案降权+分层排序,**新任务首选**。**空格键迭代的等价物**:换 seed/mode/风格词重掷,生成 ≥2 个候选再往下走。候选多时 `showcase` 出样张点名。

### 第 3 步:角色化,不是色块袋

```bash
python "$S" roles --palette 606C38,283618,FEFAE0,DDA15E,BC6C25 --semantic --css
```

输出 bg/text/accent/primary/surface + 派生语义色(success/warning/error/info),附三组对比度检查,不过关非零退出。要点:最强的色**拥有一块完整区域**,不撒成碎点缀。

### 第 4 步:机械验证(可测量与品味分离)

```bash
python "$S" score --palette ...     # 五维评分卡 /20,P0-P3 发现,<10 分非零退出
python "$S" contrast --fg ... --bg ... [--large]   # 单对核查,失败给修复建议
python "$S" blind --palette ...     # 色盲三模拟;图表/状态色必查
python "$S" slop --palette ...      # AI-slop 签名检出,命中即非零退出
python "$S" matrix --palette ... --method apca --recommend   # 全对矩阵(APCA)+最优配对
python "$S" semantic --count 8 --base 2A9D8F        # 色盲安全分类色(图表/数据可视化)
```

图表另加:只用明度阶梯区分数据(ramp),形状/标注冗余编码,红绿永不作唯一区分。

### 第 5 步:导出 token

```bash
python "$S" export --palette ... --format css|tailwind|json|svg
python "$S" mutate --palette ... --shade -20 --sat +5 --hue 15 --temp +30
```

### 第 6 步:五镜自审(强制闸门)

```bash
python "$S" card --palette ... --name "项目名" --out card.html   # 色板卡+mockup
python "$S" critique --palette ... [--evidence evidence.json] --out report.md   # 五镜报告生成器
python "$S" doctor                                 # 环境体检
python "$SDIR/scripts/lint_page.py" page.html --palette <声明色板> --floor 12   # 交付审计
```

**必须**截图贴进对话,按 `references/critique.md` **五镜头**逐镜裁决(意图语域→构成→信息→色彩→文字):每条 PASS/FAIL 指向具体元素+引用原则+证据;FAIL 未修不交付;修复有界。HTML 交付前必跑 lint_page。

闸门链:

| 步骤 | 工具 | 把什么 |
|---|---|---|
| 1 色板 | `score` | 五维+档案违例 |
| 2 构建 | 任意 | — |
| 3 HTML 纪律 | `lint_page` | 漂移/黑名单/字号/剂量 |
| 4 渲染证据 | `render_probe.js` + `lint_page --render` | 主题/剂量/对比/字号实测 |
| 5 候选 | `make_variants` | ≥2 候选对比页 |
| 6 五镜截图 | 人+agent | 视线顺序/密度/构图 |

渲染探针降级路径:无浏览器工具时跳过步骤 4,以截图五镜为最低门槛,并在交付说明中注明"渲染实测未跑"。

用户否决时先做**尸检**(失败模式写回 critique.md)再重设计。正式交付按用户所在环境的验收流程执行。

## 裁决回写与自定义

- **已验收设计入库**:`python "$S" house --name "项目定稿" --hexes ... --from-proj 项目名` —— 进库并自动加权,match 优先推荐。
- **自定义语域**:编辑 `profile.json` 的 `registers`(键=语域名,值含 theme/style_tags/accent_max_area),`match --register` 即可用;新领域 = 加词条,不是改代码。
- **自检**:`python "$S" selftest` —— WCAG 边界值/OKLCH 往返/slop 签名全量自检,非零退出 = 引擎不可信。

## 参考文档(30 秒路由)

| 任务 | 去哪 |
|---|---|
| 写否定清单/识别 AI 味 | anti-slop.md(黑名单表+模板) |
| 自审一张页面 | critique.md(五镜+裁决输出格式) |
| 查谐和规则/对比度公式/色彩语义 | color-theory.md |
| 快速找某条法则 | craft-rules.md(法则卡) |
| 扩库/理解选板方法论 | curation.md |
| 再收割 the source site 数据 | harvest-playbook.md(含 5 个实测坑) |

| 文件 | 内容 |
|---|---|
| `references/critique.md` | 五镜头审核法+命名失败模式+尸检档案 |
| `references/craft-rules.md` | 配色法则卡(五镜审核的速查面) |
| `references/color-theory.md` | 谐和规则/OKLCH/明度架构/60-30-10/WCAG 公式/色彩语义 |
| `references/anti-slop.md` | AI-slop 黑名单与证据链 |
| `references/curation.md` | 选板方法论细则+扩库流水线 |
| `references/harvest-playbook.md` | 源站数据收割配方(5 个实测坑) |

## 选板方法论

三层过滤:①人群信号(源站官方榜单+点赞分层+跨页重复)②客观质量门(只拦客观坏:平坦明度/无可读对拒;色盲碰撞/slop 打旗)③使用时上下文自审(最终裁决)。**没有人能先验知道"好看"**——库负责起跑线,裁决在上下文。细则见 `references/curation.md`。
