# 一次性补丁脚本（不参与构建）

这里两个 `patch_*.py` 是历史过程里用来就地改写其他脚本的一次性补丁：

| 文件 | 作用 | 改写目标 |
|---|---|---|
| `patch_prepare_multi.py` | 给 `prepare_multi.py` 加 `kernel` 字段、`im` 材质、PetBase 材质族分支 | `tools/charextract/prepare_multi.py` |
| `patch_pet_body.py` | 重写精灵 body 表面函数 | `_nrc_work/pet-port.glsl` |

**它们的改动都已经并入目标文件**，所以这两个脚本在当前代码库里不再需要运行，
路径也是硬编码的旧工作区绝对路径。

保留它们只是为了溯源：想知道某个能力是哪一步加进来的，看这里比翻 git 历史直观。
