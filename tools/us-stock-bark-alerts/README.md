# 美股均线轮动信号 → Bark 推送

每天美股收盘后使用 Yahoo Finance 复权日线检测均线交叉，并通过 Bark 向 iPhone 发通知。**只推送信号，不自动买卖股票。**

## 监控规则
- **TSLA 特斯拉**：MA5 **上穿** MA30 → 提醒卖 ORLY、买 TSLA；**下穿** → 提醒卖 TSLA、买 ORLY。
- **AAPL 苹果、SPY 标普500 ETF、QQQ 纳斯达克100 ETF、NVDA 英伟达**：分别监控自身价格与 MA225。
  - 今日收盘价**上穿**当日 MA225×**1.01** → 提醒减持 WM/WMT/TSCO/LOW/MCD/TLT，买入**触发信号的那只成长标的**。
  - 今日收盘价**下穿**当日 MA225×**0.99** → 提醒卖出**触发信号的那只成长标的**，买入六只防御资产。
- “上穿/下穿”对比**前一交易日自身对应阈值**和今日阈值；价格持续高于/低于阈值不会反复报警。1% 缓冲带内不会新发信号。
- 采用**复权收盘价**；MA 是简单移动平均。SPY/QQQ 为 ETF 代理，不是指数原值。

## 开启通知（还需要你设置 Bark Key）
1. iPhone 安装 Bark，打开 APP 复制它给你的推送 Key（不要公开分享）。
2. 当前代码位于 GitHub 仓库 bryanleeup-cmyk/ai-creative-production-lab。
3. 进入该仓库 **Settings → Secrets and variables → Actions → New repository secret**。
4. Name = **BARK_KEY**；Secret = 复制的 Bark Key。
5. 进入 **Actions → US Stock MA Signals (Bark) → Run workflow**，勾选 **test_bark**，立即发送测试推送。
6. 可选：自建 Bark 服务时设置 Actions **Variable**：BARK_SERVER = https://服务器域名，默认 https://api.day.app。

注意：不能仅把推送链接粘贴进代码；**BARK_KEY 只能保存在 Actions Secret**。

## 运行方式
工作流在工作日美东时间收盘后的 **16:37、16:52、17:07**左右多次检查。对应 UTC 定时配置会跨夏令时自动适配，脚本过滤非指定美东时间。GitHub Actions 的定时任务可能延迟或漏跑；仅交易日、且免费行情确有当日日线时才处理，拒绝使用过期日线。

通知成功后，信号键写入本目录的 state.json，通过 Actions 提交到 GitHub，以避免同一信号重复通知。手动运行可勾选 dry_run，只查信号不通知、不记录。GitHub Actions 若不能写入文件，检查 Settings → Actions → General → Workflow permissions 是否允许写入。

如公开仓库 **60 天无活动**，GitHub 可能停止定时工作流。Yahoo Finance 免费行情可能延迟、限流、缺失，不应作为高可靠自动交易依据。多个成长标的同一天可能出现相反指令，且 TSLA/ORLY 与防御组合调仓会竞争资金；实际仓位、税费、滑点、持仓和资金分配均需要人工确认。

## 本地运行
从仓库根目录：
~~~bash
pip install -r tools/us-stock-bark-alerts/requirements.txt
python -m pytest tools/us-stock-bark-alerts/tests -q
python tools/us-stock-bark-alerts/monitor.py --manual --dry-run
export BARK_KEY='自己的设备key'
python tools/us-stock-bark-alerts/monitor.py --test-bark
~~~
