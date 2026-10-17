# 移动端适配法则（Responsive Rules）

> 何时读我:产出展示型页面(落地页/showcase/文档站)需在手机端正确呈现时,或用户报"导航消失/重叠遮挡/横向滚动条"时。
> 最短路径:导航铁律→画布横滚模式→溢出定位法→验收清单。
> 回 INDEX:SKILL.md「参考文档(30 秒路由)」。

桌面精美、手机破碎,几乎总是四个可机械修复的错误:导航被隐藏、栏高写死、固定宽画布硬塞、grid 最小列超视口。
2026-10-17 入口页+showcase 双页实战沉淀(375px 视口实测)。

## 规则一:导航永不 display:none

移动端把导航链接 `display:none` 是最常见的手懒——用户失去导航("顶部导航消失了"就是它)。
正确形态:**bar 高度自适应 + 链接行横向滚动**:

```css
.bar{min-height:56px; flex-wrap:wrap; row-gap:8px; padding:10px 24px}  /* ⛔ 禁 height:58px 写死 */
nav{flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none}            /* 链接横滚,不折行不堆叠 */
nav::-webkit-scrollbar{display:none}
nav a{white-space:nowrap}                                               /* 链接文字禁折行(否则"中 文"竖排) */
```

- 栏高写死(如 height:58px)而内容折行 → 内容溢出栏外盖住 hero(重叠遮挡的第二大来源)。
- 语言/主题切换按钮组 `white-space:nowrap`,防按钮文字竖排。

## 规则二:固定宽画布 = 横向滚动画廊

桌面 mockup(手机壳/浏览器框/仪表盘)是 920px 级精细布局,压进 375px 必然破碎(显示不全/错位)。
不要重写场景做"真响应式"(成本极高、失真),用**画廊模式**:

```css
.stage{overflow-x:auto; -webkit-overflow-scrolling:touch}
.stage > *{min-width:920px}   /* 场景保持设计宽,手机左右滑动查看完整内容 */
```

页面其余部分(导航/标题/正文)正常响应式。桌面端 min-width 无副作用(容器本就 920px)。

## 规则三:grid 最小列必须 min(100%,Npx)

`repeat(auto-fit,minmax(380px,1fr))` 在 375px 视口=列最小 380px=必溢出 33px(实测案例)。
一行修正,永绝后患:

```css
grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));
```

## 规则四:溢出定位法(机械,不靠目测)

```js
// 页面级判定
document.documentElement.scrollWidth > window.innerWidth          // true = 有横向溢出
// 真凶定位:遍历元素找 right 超出视口者(排除滚动容器内部)
Array.from(document.querySelectorAll('body *'))
  .filter(e => e.getBoundingClientRect().right > window.innerWidth + 1)
```

修复后复测 scrollWidth 必须回到 ≤ innerWidth。截图截不出来的 33px,这五行代码一定找得到。

## 规则五:大字号标题也要 clamp

中文衬线大标题 62px×7 字≈470px,375px 屏必溢出。所有 display 级字号用:

```css
font-size:clamp(30px, 9.5vw, 62px);   /* 下限=最小可用字号,首选=手机实际值,上限=桌面设计值 */
```

## 验收清单(375×812 视口过这五条)

1. `scrollWidth ≤ innerWidth`(页面无横向滚动条);
2. 导航链接全部可见可用(可以横滚,不可以消失/堆叠溢出);
3. 栏高自适应,内容不溢出栏外(无遮挡 hero);
4. 固定宽画布呈横向画廊,场景内容完整(不挤压错位);
5. 按钮组/标签不竖排(white-space:nowrap 到位)。
