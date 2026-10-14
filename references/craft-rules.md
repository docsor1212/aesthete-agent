# 命名法则卡(蒸馏自 2026 年最受欢迎的设计类 skill)

来源:frontend-design(Anthropic,277K 安装)、impeccable(pbakaus,27 条确定性反模式规则)、canvas-design(Anthropic)、theme-factory(Anthropic)、web-artifacts-builder(Anthropic)、baoyu-design、accesslint。深研记录见 `coolors-research/skill-research/`。写设计 prompt/自审时直接引用法则名。

## 方向类

- **「The brief wins」**(impeccable):用户钉死的美学/年代/材质/字体/色板是绑定约束,即使它与饱和度警告冲突也要照办。把明确的 brief 拧向自己的口味=失败。
- **「哲学先行」**(canvas-design):先命名 1-2 词的美学运动并写一句宣言,再做设计。"Chromatic Silence"式的名字逼出具体选择,模糊=中位数。
- **「中位数陷阱」**(prg.sh/frontend-design/web-artifacts-builder/impeccable 四方独立确认):模糊指令下模型输出训练数据中位数,"那个中位数是紫色的"。修法=参照美学+显式维度+否定清单。

## 色彩类

- **「角色,不是色块袋」**(impeccable colorize):配色是角色体系——canvas/surface、主/次文本、action/focus/selection、border/separator、success/warning/error/info、数据类别——不是一个随手抓的 hex 列表。→ `roles --semantic`
- **「稀缺即力量」**(impeccable: Rarity gives an accent force):点缀色占比越大力量越小;最强的色应拥有一块完整区域,而不是撒成碎片。10% 是脚手架不是法律——比例追随 brief。
- **「可测量与品味分离」**(impeccable audit / accesslint):对比度、色盲碰撞、明度跨度交给机器;好不好看留给上下文自审与用户。→ `score` 与 `slop` 只报机械发现,不判审美。
- **「端点降饱和」**(impeccable: reduce chroma near white and black):做明度阶梯时,接近纯白/纯黑的端点要收饱和度,不要为数学均匀保高饱和。→ `ramp`
- **「显式色优于透明叠加」**(impeccable):宁可写明确色值,不用半透明叠加链——alpha 会让对比度随背景漂移。
- **「暗色=重新构图」**(impeccable/baoyu):暗色主题是显式设计海拔与对比,不是把浅色主题机械反色。→ color-theory.md 的 [data-theme=dark] 架构
- **「彩色面上的次级文字从色调派生」**(impeccable):在彩色表面写次级文字,用前景/表面色相派生,不用发灰的通用灰。

## 流程类

- **「有界验证」**(impeccable):完整做完→一轮批量检查(桌面+移动一起)→一轮批量修→最多再确认一次→停。开放式自检循环是在烧钱做更差的活。
- **「第二遍只精炼」**(canvas-design):想加新元素时停下来问"怎么让已有的更像一件作品"。禁"再加个滤镜/再画个形状"式修改。
- **「样张+点名」**(theme-factory):候选≥3 时,渲染命名样张让用户按名字挑,不要用文字描述色板让用户想象。→ `showcase`
- **「视觉反馈回路是最高杠杆」**(Composio 榜单评 Playwright;baoyu/frontend-design 同义):盲改必翻车,一切以截图证据收敛。→ card + emitImage
- **「新项目=新提问」**(baoyu-design):别把上次会话的视觉方向当这次的默认;可作建议,须用户确认。

## 已并入本 skill 的实现对照

| 法则 | 落点 |
|---|---|
| 角色,不是色块袋 | `roles --semantic` |
| 端点降饱和 | `ramp` |
| 可测量与品味分离 | `score`(0-4 锚点+P0-P3,/20) |
| 样张+点名 | `showcase` |
| 哲学先行 | 六步法第 1 步 |
| 有界验证 | 铁律 4 |
| 中位数陷阱 | `slop` 四签名 + anti-slop 黑名单 |
