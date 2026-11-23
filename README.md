给每个团队分配了主题之后，有个团队订阅到了别人的支付事件：主题解析允许空段，连续点被当成合法主题；通配匹配把多层通配当作单层，权限被意外放大；通配匹配允许前缀命中，团队前缀相同的主题被放行；订阅判定只看允许规则，忽略拒绝规则；发布与订阅共用同一套规则，只读团队能发消息；死信队列不单独授权，任意团队可读；订阅数上限不校验，可无限订阅拖垮代理；主题匹配忽略大小写折叠策略不一致，大小写变体绕过；策略校验不检查多层通配是否过宽；批量判定复用匹配结果，后一个请求命中前一个请求的主题。bus/acl.py 是核心，tests/test_acl.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

sec-queue-acl

这是一个单文件修复题。上面第一行就是完整题面，不要改动 tests 目录。

字段表
字段            内容
安全            安全
漏洞检测与攻防  漏洞检测与攻防
题型            Bugfix
运行时          Python 3, pytest
外部依赖        无外部依赖

文件
README.md
pyproject.toml
src/bus/__init__.py
src/bus/acl.py
tests/test_acl.py

布局说明
pyproject.toml 中的 tool.pytest.ini_options 把 src 加入导入路径，所以这是 pyproject 指定导入路径的 src 布局。测试通过 bus.acl 导入实现，无需安装包。

运行方式
在仓库根目录执行：

    pytest tests -q

初始输出必须恰好是 15 failed，0 error。15 个测试都会因为 8 个桩抛出 NotImplementedError 而变红。修复入口是 src/bus/acl.py，按题面顺序修掉 10 个缺陷，让 15 个测试逐个转绿。tests/test_acl.py 不可修改。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |
