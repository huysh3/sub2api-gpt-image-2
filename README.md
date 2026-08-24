# codex-sub2api-image-gen

一个给 Codex 使用的图片生成 Skill：当内置 `$imagegen` 不可用、缺失或被自定义 provider / sub2api 拦截时，改用当前 Codex provider 直接调用兼容的 Images API。

![工作原理](assets/sub2api-imagegen-principle.png)

## 特点

- 自动读取当前 Codex provider 的 `base_url`、`experimental_bearer_token` 和自定义请求头。
- 使用非 OpenAI SDK 的 User-Agent，绕开已知的 sub2api / Cloudflare SDK 请求头拦截。
- 支持图片生成、图片编辑、无费用连通性检查和脱敏 dry run。
- 仅依赖 Python 标准库，不安装 OpenAI SDK。
- 默认给 `gpt-image-2` 传入 `3840x2160`；服务端返回多大就原样保存多大，不在本地超分、缩放、补边或重采样。

## 环境要求

- Codex
- Python 3.11+
- 已配置且支持 Images API 的 Codex custom provider / sub2api

## 安装

把整个仓库直接克隆到 Skill 目录：

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/huysh3/sub2api-gpt-image-2.git ~/.agents/skills/sub2api-imagegen
```

仓库根目录就是 Skill 根目录，不需要绑定或创建专属 Agent。重启 Codex 或开启一个新任务即可使用。

## 使用

直接在 Codex 中调用：

```text
$sub2api-imagegen 帮我生成一张雨夜霓虹街道的横版图片
```

编辑已有图片也是一句话：

```text
$sub2api-imagegen 把 input.png 的背景换成日落，主体保持不变
```

Codex 当前显式调用 Skill 使用 `$skill-name`；不需要手动执行底层 Python 命令。只有排查 provider 连通性时才需要：

```bash
python3 ~/.agents/skills/sub2api-imagegen/scripts/sub2api_image_gen.py doctor
```

## 分辨率说明

这里的 `3840x2160` 是 **4K 入参**，不是 4K 输出承诺。不同 sub2api 账号路由或兼容 provider 可能返回不同尺寸；客户端会检测实际 PNG 尺寸、提示差异，并原样保存服务端字节。当前已观察到 OpenAI OAuth 路由接受 `3840x2160`，但返回 `1672x941`。

依据：[OpenAI `gpt-image-2` 常用尺寸](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide#popular-gpt-image-2-sizes)；[sub2api OAuth 实际尺寸测试](https://github.com/Wei-Shaw/sub2api/blob/d45135d87df16d48637f04ccd245727bc955ba54/backend/internal/service/openai_images_actual_size_test.go#L42-L54)。

## 安全说明

- 凭证只从本机环境变量或 Codex 配置读取，不写入仓库或生成文件。
- 客户端不主动打印 bearer token 或完整请求头；dry run 也不包含凭证。
- `doctor` 和 dry run 会显示当前 provider 的 base URL，API 错误会包含上游返回的错误正文。公开日志前请检查其中是否包含私人域名、路径或上游回显的信息。
- 不要提交 `.env`、`config.toml`、API key、cookie 或真实请求日志；仓库自带的 `.gitignore` 会忽略常见本地凭证文件。

## 已知限制

- `doctor` 只能验证路由连通和模型列表，不能保证付费生成一定成功。
- 不自动重试付费请求。
- `gpt-image-2` 不支持原生透明输出；透明图片需显式切换到 `gpt-image-1.5`。
- 实际支持的模型、尺寸和质量参数取决于上游兼容实现。

## License

本项目采用 [MIT License](LICENSE)。
