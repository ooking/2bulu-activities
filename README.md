# 2bulu-cf

2bulu 深圳约伴在 Cloudflare 上的代码：查询页 + 数据接口 Worker。

## 结构

- `web/bulu-web.html` — 移动端查询页（https://2bulu.168939.xyz），直调接口 Worker 拿实时数据
- `workers/bulu-worker.js` — 数据接口 Worker（https://2bulu-api.168939.xyz），从 D1 `2bulu-activities` 查数据
- `deploy.py` — 一键发布脚本
- `.github/workflows/deploy.yml` — push 到 main 自动发布

## 本地发布

```bash
export CF_API_TOKEN=...        # 需 Account -> Workers Scripts:Edit, D1:Edit
export CF_ACCOUNT_ID=...       # 可选，默认已填
python3 deploy.py              # 发布接口 + 查询页
python3 deploy.py --domains    # 额外确保自定义域名绑定（需 Token 有 DNS:Edit）
```

## GitHub Actions 自动发布

仓库 Settings -> Secrets and variables -> Actions 里加两个 secret：

- `CLOUDFLARE_API_TOKEN` — 在 Cloudflare 后台 My Profile -> API Tokens 新建，
  权限：Account -> Workers Scripts:Edit、D1:Edit
- `CLOUDFLARE_ACCOUNT_ID` — `2f310a5cd7c2c533e9edf3d31f97fe88`

之后 push 到 `main` 分支（或手动 Run workflow）即自动发布。

## 说明

- 每小时增量同步脚本 `sync_to_d1.py` 留在抓取流水线里（依赖本机安全存储的凭证），不在此仓库。
- D1 数据库 `2bulu-activities` 的全量导入是一次性操作，不走流水线。
