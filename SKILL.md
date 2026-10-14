---
version: 0.2.1
name: aesthete-agent
description: AI 的前端美学引擎(Aesthete Agent)。写 UI/HTML、SVG 幻灯片、视频封面、图表、海报等任何需要颜色的设计任务时,用六步法出配色:命名美学宣言→语域判定→选来源(87 板 coolors 实证库 match 匹配/OKLCH 谐和生成/图像取色/明度阶梯)→60-30-10 角色化(含语义色)→score 五维评分卡+WCAG 对比度+色盲模拟机械验证→card 上下文预览+五镜自审(有界修复)。内置 AI-slop 检测(紫渐变/中位数陷阱)、lint_page 交付审计、profile.json 偏好学习档案(用户每次裁决自动生效)。纯标准库离线可用。触发词:配色、调色板、配色方案、颜色搭配、前端美学、UI配色、设计美学、color palette、color scheme、design aesthetics、hex、对比度、WCAG、色盲、视觉审美、aesthete-agent。
---

# aesthete-agent — 离线配色引擎 v2(coolors 方法论 × 顶级设计 skill 精髓)

大模型配色差的根因已实证:模型把 hex 当文本操作、输出训练数据中位数(Tailwind 靛蓝→紫渐变,"该中位数是紫色的"被 frontend-design / web-artifacts-builder / impeccable 三方独立确认)、无法真正"看见"颜色(ColorBench: VLM 色觉理解整体有限)。修法不是换模型,而是**把品味外包给流程**:哲学先行、角色化、机械验证、上下文自审。本 skill 把 coolors.co 的产品逻辑与顶级设计 skill 的纪律离线化。

⛔ 铁律:
1. **禁止裸写配色**。任何设计任务的配色必须走六步法,第 6 步(上下文自审)不可跳过。
2. **禁止运行时访问 coolors.co**——无公开 API,curl 全被 Cloudflare 403(2026-10 实测);数据已离线内置。
3. **The brief wins**(impeccable 铁律):用户/上游指定的颜色与美学方向是绑定约束,本 skill 围绕它服务,不越权重配。既定锁定色系管线(NPG / Bees & Honey / GLM 黄蓝)不受本 skill 改配。
4. **有界验证**(impeccable 纪律):完整做完→一轮批量自审→一轮批量修复→最多再确认一次→**停止打磨**。开放式反复自审烧钱且产出更差。
5. **候选纪律**:送用户裁决必须 ≥2 个整页候选(`make_variants.py` 合成对比页);单方案不得送审,脚本退出码把关。
6. **裁决回写**(学习机制):用户每次接受/否决,必须落 `profile.json`(机读,match/score/lint 自动消费)与 `critique.md` 尸检(可迁移失败模式)——不回写=本轮白干,skill 永远不长。

## 六步法

### 第 1 步:命名美学宣言(canvas-design 精髓)

先给这套配色起一个 **1-2 词的运动名** + 一句话宣言,再动手:"药圃手账——陶罐褐、晒干草本绿、桑皮纸米黄,全部低饱和,像被时间晒过"。模糊的"好看"必然产出中位数;命名逼你做具体选择。宣言包含:
- **语域判定**(镜 0,critique.md):先答三问——给谁看/什么场景看/3 秒带走什么。视觉语域必须与内容领域同域(儿科教学=daylight 清晰,不是深夜金)。**用户既有审美档案(如素雅/浅底/留白/大幽灵数字)是最高优先约束,先查再写;隐喻契合救不了语域错配**;
- **参照美学**(最有效的一招):"1970s 滑雪小屋:焦橙、牛油果绿、暖棕";
- **明暗架构**:浅色底还是深色底?文字永远最深/最浅;
- **色彩剂量**(impeccable: name the color dosage):点缀色全页占比 ≤10%,"稀缺即力量";
- **否定清单**:从 `references/anti-slop.md` 挑适用项写进 prompt(推理期否定有效);
- 60-30-10 只是**默认脚手架,不是法律**(impeccable: strategy must follow the brief rather than a fixed percentage rule)。

### 第 2 步:选来源(四条路)

```bash
S="scripts/palette_forge.py"  # 在本 skill 目录下执行
python "$S" match --brief "儿科临床教学页" --limit 6           # A' brief匹配:自动判语域+档案降权(首选)
python "$S" search --style warm,pastel --no-flags --limit 6   # A 收割库(87板,点赞分层)
python "$S" harmony --base 780000 --mode complementary --theme light  # B OKLCH 谐和生成
python "$S" extract reference.png --n 6                        # C 图像取色(需 Pillow)
python "$S" ramp --base 2A9D8F --steps 7                       # D 明度阶梯(图表/热图)
```

A'=自然语言 brief → 语域判定(关键词词典)+档案深色降权+点赞分层排序,**新任务首选入口**。A=被人群收藏过的组合,B=受控确定性变体,C=与素材天然协调,D=单色相阶梯(图表序数色首选)。**空格键迭代的等价物**:换 seed/mode/风格词重掷,生成 ≥2 个候选再往下走。候选多时用 `showcase` 出样张让用户点名(theme-factory 模式):

```bash
python "$S" showcase --style pastel --min-likes 5000 --limit 8 --out showcase.html
```

### 第 3 步:角色化,不是色块袋(impeccable colorize 精髓)

```bash
python "$S" roles --palette 606C38,283618,FEFAE0,DDA15E,BC6C25 --semantic --css
```

输出完整角色体系:bg/text/accent/primary/surface + 派生语义色(success/warning/error/info,继承点缀色的明度饱和性格)。三组对比度检查,不过关非零退出。要点:让最强的色**拥有一块完整区域**而不是撒成碎点缀;中性灰本身合法,不必硬染色。

### 第 4 步:机械验证(可测量与品味分离——impeccable audit 精髓)

```bash
python "$S" score --palette ...     # 五维评分卡:ARCHITECTURE/READABILITY/CB-SAFETY/SAT-DISCIPLINE/UNIQUENESS,0-4锚点,/20,带P0-P3发现,<10分或含P0则非零退出
python "$S" contrast --fg ... --bg ... [--large]   # 单对精确核查(失败给修复建议)
python "$S" blind --palette ...     # 色盲模拟;图表/状态色必查
```

图表另加:只用明度阶梯区分数据(ramp 命令),形状/标注冗余编码,红绿永不作唯一区分。

### 第 5 步:导出 token

```bash
python "$S" export --palette ... --format css|tailwind|json|svg
python "$S" mutate --palette ... --shade -20 --sat +5 --hue 15 --temp +30
```

### 第 6 步:五镜自审(强制闸门,证据化裁决)

```bash
python "$S" card --palette ... --name "项目名" --out card.html   # 色块卡+按钮/图表 mockup
```

**必须**截图/emitImage 贴进对话,按 `references/critique.md` 的**五镜头**(意图语域→构成→信息→色彩→文字)逐镜裁决:每条 PASS/FAIL 都要指向具体元素+引用原则+证据;FAIL 未修不交付;修复有界(一轮批量修,最多再确认一次)。HTML 交付前加一道**静态审计闸门**(机制,退出码说话):

```bash
python "$S/lint_page.py" page.html --palette <声明色板> --floor 12   # 色板漂移/黑名单/字号下限/渐变与emoji剂量
```

闸门链:`score`(色板+档案)→ build → `lint_page`(HTML 纪律)→ `render_probe.js`(浏览器 evaluate 采集渲染证据,存 evidence.json 后 `lint_page --render` 消费)→ `make_variants`(≥2 候选对比页)→ 截图五镜(视线顺序/密度/构图)。用户否决时先做**尸检**(可迁移失败模式写回 critique.md)再重设计——偏好是输入,方法是资产。正式交付物再走既有 visual-judge 闸门。

## 配色库是怎么选出来的(选板方法论)

**没有人能先验知道"好看"**,所以库用三层过滤,各管各的:
1. **人群信号**:只收 coolors 官方榜单页(trending/popular/latest)的真实调色板,tier 按点赞分层(★★★≥50K/★★≥20K/★>0/new);跨页重复出现记 occurrences(多次上榜=更强背书)。likes 是"被收藏欲"信号,不等于专业适配。
2. **客观质量门**:只拦"客观坏",不判"主观好"——明度全平(span<0.15)拒、无可读文字对(<4.5:1)拒;色盲严重碰撞(<0.02)/slop 签名/窄明度打旗不拒。首批 116 去重后 87 入库、29 被拒(全部拒得有据,如 max 对比 2.15:1 的板)。
3. **使用时上下文自审**:最终裁决永远发生在第 6 步的 mockup 里+用户眼前。

扩库/重跑流水线见 `references/curation.md`;收割配方(含 5 个实测坑)见 `references/harvest-coolors.md`。

## 与其他 skill 的协作

- **frontend-design**(277K 安装,方向/反模板):它要 token 系统"4-6 个具名 hex"——本 skill 第 1-3 步就是其供弹管线;它的 AI 三大默认长相清单已并入 anti-slop。
- **baoyu-design**(设计工件):其"优先品牌色,否则 oklch 生成和谐色"由 harmony/ramp 落实;产出 CSS 变量直接写进其 design system tokens(:root 变量+[data-theme=dark] 翻转架构见 color-theory.md)。
- **impeccable**(27 条确定性反模式规则):其色彩法则(colorize)已蒸馏进 `references/craft-rules.md`;score 的 0-4 锚点+P0-P3 格式来自其 audit。
- **theme-factory**(10 主题库模式):showcase 命令即其"样张+点名"模式。
- **glm-deck / medical-svg-slides / medical-doc-html**:有锁定色系,不动。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/critique.md` | 五镜头审核法+命名失败模式+尸检档案 |
| `references/craft-rules.md` | 七大设计 skill 蒸馏的命名法则卡(带出处) |
| `references/color-theory.md` | 谐和规则/OKLCH/明度架构/60-30-10/WCAG 公式/色彩语义/ramp 规则 |
| `references/anti-slop.md` | AI-slop 证据链(三源)与黑名单 |
| `references/curation.md` | 选板方法论细则 + 扩库流水线用法 |
| `references/pipeline-integration.md` | iei-cover/glm-deck 流水线接入点(2026-10 双链路实战验收通过) |
| `references/harvest-coolors.md` | 从 coolors.co 收割的浏览器配方(5 个实测坑) |
