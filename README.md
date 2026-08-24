# codex-sub2api-image-gen

一个给 Codex 使用的图片生成 Skill：当内置 `$imagegen` 不可用、缺失或被自定义 provider / sub2api 拦截时，改用当前 Codex provider 直接调用兼容的 Images API。

![工作原理](output/imagegen/sub2api-imagegen-principle-pixel-islands-v2.png)

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

仓库内使用：保留当前目录结构，Codex 会从 `.agents/skills/sub2api-imagegen` 发现 Skill。

安装到用户目录：

```bash
mkdir -p ~/.agents/skills
cp -R .agents/skills/sub2api-imagegen ~/.agents/skills/
```

重启 Codex 或开启一个新任务后，通过 `$sub2api-imagegen` 使用。

## 使用

先检查当前路由和模型是否可用；此命令不会生成图片：

```bash
python3 .agents/skills/sub2api-imagegen/scripts/sub2api_image_gen.py doctor
```

生成图片：

```bash
python3 .agents/skills/sub2api-imagegen/scripts/sub2api_image_gen.py generate \
  --prompt "A ceramic coffee mug in soft studio light; no logo, text, or watermark" \
  --quality medium \
  --out output/imagegen/mug.png
```

编辑图片：

```bash
python3 .agents/skills/sub2api-imagegen/scripts/sub2api_image_gen.py edit \
  --image input.png \
  --prompt "Replace only the background with a warm sunset; keep the product and edges unchanged" \
  --out output/imagegen/sunset-edit.png
```

只查看脱敏后的请求，不发起网络请求或产生图片费用：

```bash
python3 .agents/skills/sub2api-imagegen/scripts/sub2api_image_gen.py generate \
  --prompt "test image" \
  --dry-run
```

完整参数可通过子命令的 `--help` 查看。环境变量 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY` 优先于 Codex 配置；也可用 `--provider` 或 `--config` 指定其他本地配置。

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
