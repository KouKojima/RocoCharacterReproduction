# RocoCharacterReproduction

《洛克王国：世界》人物渲染的逆向复现。

从本地客户端的 PAK 资源里直接提取人物的网格、材质、贴图与原版动作，用字节码还原的着色器逻辑在浏览器里重建渲染，最终打包成**一个可离线双击打开的 HTML 文件**。

当前交付三个角色：

| 角色 | 资源 ID | 顶点 | 三角面 | 贴图 | 原版动作 | 骨骼 | 附加姿势 | 面部曲线 | 变形目标 |
|---|---|---|---|---|---|---|---|---|---|
| 参考角色 | `NPC_00401` | 13,643 | 17,844 | 14 | 37 | 107 | 109 | 108 | 0 |
| 路易斯 | `NPC_01101` | 8,522 | 11,400 | 14 | 37 | 104 | 176 | 175 | 34 |
| 伊里斯（人形态） | `NPC_06201` | 11,722 | 16,344 | 17 | 96 | 120 | 0 | 113 | 42 |

**脸会动。**原版的脸不是骨骼动的，是 blend shape（变形目标）驱动的：每个动作序列自带以变形目标命名的浮点曲线，曲线值就是权重。所以选中「对话动作 · World_Dialogue_1」，嘴就会跟着开合——这不是我们额外造的动画，是原版数据本身的行为。路易斯的 104 根骨骼里连一根下巴/下颌/唇骨都没有，嘴在骨骼上本来就无路可走。

`dist/原版人物渲染预览.html`（93.4 MB）是成品：双击即可打开，无需服务器、无需联网。该文件由下方「快速上手」的打包步骤在本地生成，**不随仓库分发**（避免大文件入库与素材分发风险）。

> **版权提示**
> `dist/` 里的单文件内联了从游戏客户端提取的模型与贴图（base64 封装）。这些素材的著作权属于游戏权利方。本仓库仅供技术研究与个人学习使用；如果你要公开分发或商用，请自行确认合规性，或只取 `tools/` 与 `preview/` 中的源码部分重新用你自己的资源构建。

---

## 目录结构

```
├── tools/                      提取与装配工具
│   ├── NrcChar/                C# 资源提取器（网格 / 材质 / 贴图 / 动作 / 对话曲线）
│   ├── CharScan/               角色资源扫描器
│   ├── LibScanner/             库与资源枚举器
│   └── charextract/            Python 装配管线（材质解析 / 动作准备 / 着色器转译 / 打包）
├── preview/                    浏览器预览前端源码
│   ├── app.js materials.js     渲染与材质
│   ├── animation.js assets.js  原版动作与资源加载
│   ├── build.mjs               esbuild 打包入口
│   ├── pet-*.html              精灵着色器指令级对拍台（自包含，研究留档）
│   └── pet/                    精灵着色器 GLSL 与对拍样本（研究留档，不进成品）
├── CUE4Parse_src/              第三方 UE4 资源解析库（vendored，FabianFG/CUE4Parse）
├── manifest/                   角色装配清单
├── build/                      一键构建脚本
└── dist/                       打包产物（预览单文件，本地生成，不入库）
```

## 文档

| 文件 | 内容 |
|---|---|
| [docs/01-角色数据事实.md](docs/01-角色数据事实.md) | 三个角色从资源里读出来的确切数据 |
| [docs/02-材质与着色器还原.md](docs/02-材质与着色器还原.md) | 材质链、常量缓冲、像素着色器还原与对拍 |
| [docs/03-动画还原.md](docs/03-动画还原.md) | ACL 动作解码、骨骼蒙皮、变形目标表情 |
| [docs/04-复现步骤.md](docs/04-复现步骤.md) | 从本地客户端到成品 HTML 的完整流程 |
| [docs/05-未完成与限制.md](docs/05-未完成与限制.md) | **还没做到的部分，逐条列明** |

## 快速上手

想看效果：运行下面的打包命令生成 `dist/原版人物渲染预览.html`，再双击打开（成品不随仓库分发）。

想自己构建：

```powershell
# 1. 需要 .NET 10、Python 3.10+、Node 18+
# 2. 把轻量包里的 CUE4Parse-Natives.dll 放到 native/（见 docs/04）
# 3. 提取角色（--textures / --clips 必须是真实存在的资源名）
dotnet run --project tools/NrcChar -c Release -- --paks <游戏>\Win64\NRC\Content\Paks --out work\npc06201 --key <base-key.bin> --npc NPC_06201 --textures <...> --clips <...> model textures anim poses dialogue
# 4. 装配 → 导出变形目标 → 构建 → 打包
python tools/charextract/prepare_multi.py --data <work> --materials <materials> --shaders <shaders> --manifest manifest/characters.manifest.json --out <out>
python tools/charextract/prepare_morph.py --data <work> --chars <work>/chars --out <out>/preview/assets
node preview/build.mjs
python tools/charextract/pack_multi.py --data <out> --code preview
```

> `prepare_morph.py` 必须排在 `prepare_multi.py` **之后**——后者会重建 `<out>/assets/<角色>/animation/`。它从 `chars/<角色>/animation-research/` 里读 `morph-deltas.bin` 与原生 clip 的浮点曲线，按名字配对后写到 `<out>/assets/<角色>/morph/`。没有变形目标的角色（如 `NPC_00401`）自动跳过，不报错。

细节见 [docs/04-复现步骤.md](docs/04-复现步骤.md)。

## 验证结论

- 精灵（PetBase）像素着色器：**逐指令对拍全部 PASS** —— body 181/181、body1 165、eyes 178、outline 104 条可执行指令，8 组样本 × r0–r3 全寄存器逐分量比对，误差 ≤ 1e-4；整帧对拍最大绝对误差 1.12e-7。
- 人形动作蒙皮校验：`passed = true`，参考蒙皮误差 1.83e-05 cm，四元数范数误差 1.19e-07，权重和 [1.0, 1.0000001]。
- 变形目标：`morph-deltas.bin` 的 magic / 偏移 / 顶点数逐目标校验通过；伊里斯 42 个、路易斯 34 个目标，单目标影响 42–524 / 39–457 个顶点；命中真实变形目标的曲线 535 / 125 条，关键帧 16,121 / 2,175 个，插值以 `RCIM_Cubic` 为主（走 Hermite 切线求值）。
- 浏览器回归：三个角色均 0 console error / 0 warning，142–144 FPS（WebGL 2）。
- 表情 A/B（同一帧对照，伊里斯 `World_Dialogue_1`，时间轴 0.567 ≈ t = 2.27 s）：**变形目标开 → 嘴张开、眉毛变化；变形目标关 → 嘴闭合成一条细线、眉毛回到中性。**「对话动作」自带 14 条命中变形目标的曲线，所以选它嘴就会动。

详细数据见 [docs/02](docs/02-材质与着色器还原.md) 与 [docs/03](docs/03-动画还原.md)。

## 第三方依赖

- [FabianFG/CUE4Parse](https://github.com/FabianFG/CUE4Parse) —— UE4 资源解析，vendored 在 `CUE4Parse_src/`，遵循其自带 LICENSE。
- [three.js](https://threejs.org) 0.180.0、[esbuild](https://esbuild.github.io) 0.25.11 —— 前端构建，见 `preview/package.json`。
- ACL（nfrechette/acl）—— 动作压缩解码，由轻量包提供的 `CUE4Parse-Natives.dll` 承载。

## 致谢

轻量包 `nrc-lightweight-kit` 提供了 PAK 挂载、密钥与原生解码库的接入方式，是整条逆向链路的起点。
