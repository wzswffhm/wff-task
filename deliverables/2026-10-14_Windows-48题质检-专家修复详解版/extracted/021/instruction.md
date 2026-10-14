我们有个 Windows 本地命名管道服务，客户端遇到长消息和中文时会把一条报文读坏。请修好 workspace/candidate.ps1。它连接外部已启动的服务端，不自己启动服务。

入口参数是 -PipeName（不带 \\.\pipe\ 前缀的唯一管道名）、-Messages（string[]，每个元素是一段合法 JSON 文本，默认空数组）、-TimeoutMs（100 到 15000 的整数，默认 5000）。JSON 文本本身可以是空字符串的 JSON 表示 `""`、对象、数组或数字，可以有中文、emoji、格式化换行或空白。要保留每个元素原来的文本，不能解析后重新序列化它。

服务端是本机当前用户可访问的双向 Windows NamedPipe，使用 Message transmission mode。每次发送调用对应一个完整 UTF-8 JSON 报文，没有 BOM、长度头、分隔换行或额外终止字节；一条报文可能超过一次读取的缓冲区。以下字段名区分大小写，序号从 0 开始。

连接后先接收服务端的 {"kind":"ready"}。然后按 Messages 顺序发送 {"kind":"data","seq":i,"payload":原文本}，每发送一条都等服务端对应的 {"kind":"ack","seq":i,"payload":原文本}，确认后才发下一条。所有元素都确认后发送 {"kind":"complete","count":元素数}；只有读到服务端的 {"kind":"done","count":同一个元素数} 才算完成。空数组也必须完成 ready/complete/done 握手。JSON 报文的字段顺序及空白无要求。

返回且只返回一个对象：Status="completed" 或 "timeout"；Acks 是 string[]，包含已收到正确 ACK 的原文本，顺序不变。TimeoutMs 是从调用开始计量的整体通信期限，涵盖连接、ready、消息传输、ACK 和 done；服务端不出现、停在任一步或者在 done 前断开时返回 timeout，保留之前已确认的 Acks，结束并关闭管道。不能靠固定等待时间推断服务已健康或消息已结束，不输出日志，不访问网络或改动工作区其他文件。

服务端使用上述协议且输入可信；不要求处理畸形协议、超过 1MB 的单条报文或其他用户的服务。验收使用真实 Windows 管道和外部独立服务进程。环境是 Windows Server 2022 x64 build 20348、PowerShell 7.5.10、NTFS，离线运行。只修改 candidate.ps1；保持这个参数入口。
