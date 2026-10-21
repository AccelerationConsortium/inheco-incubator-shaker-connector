# 从零构建 INHECO Shaker 的 SiLA2 Connector

适用设备：照片中的 INHECO Incubator Shaker MP，PN 7300013，Rev.04。
项目版本：0.2.0。教程日期：2026-10-21。

**当前状态：原生串口后端、SiLA2 接口、模拟器和离线测试已实现；尚未在你的 Mac 或实物 shaker 上验收。**
“代码写完”和“设备已经验证可用”是两件不同的事。现在不需要占用设备，就能完成本教程的软件部分。

## 1. 先认识我们在做什么

Connector 可以理解为一名翻译。上游软件说“打开第 0 层抽屉”，翻译把它变为设备认识的字节；设备回答后，翻译再把结果交回上游。

完整路径是：

1. 人或工作流在 SiLA 客户端发出 OpenDrawer(Address=0)。
2. UniteLabs CDK 接收网络请求，确认参数类型。
3. `features/shaker_controller.py` 找到对应 Python 方法。
4. `io/protocol.py` 检查该层是否已初始化、振荡是否停止。
5. `io/serial_bus.py` 排队取得 USB 总线使用权。
6. `io/wire.py` 生成包含地址、命令和 CRC 的字节包。
7. Mac 经 USB 把包发送给 shaker 的控制器。
8. 控制器执行，返回完成信息或错误。
9. Connector 再读抽屉状态，确认已打开，然后结束这次 SiLA 命令。

SiLA2 是电脑之间约定怎样请求功能、传递参数和报告结果的接口。设备原有固件不因此变成 SiLA2；SiLA2 服务运行在 Mac 上。UniteLabs CDK 帮我们处理服务、接口描述和网络调用。Python 是实现翻译逻辑的语言。USB 是电脑到设备的物理连接。串口是 USB 在操作系统中提供的通信通道。

## 2. 为什么不能只写一个“开始振荡”函数

设备有三个不同层次的“成功”：

- 命令被收到：只能证明通信发生了。
- 控制器完成命令并返回成功：说明固件接受了这次操作。
- 设备状态符合要求：例如抽屉报告打开、振荡报告停止。

即使最后一项成立，也不能证明液体混合充分或样品已经达到设定温度。因此本项目的 StartShaking 确认的是启用状态；WaitForTemperature 读取的是设备主传感器，不是样品中的温度。

这一点会直接影响实验软件的正确性。不能收到 ACK 就宣布实验完成。

## 3. 文件、目录和命令行的基本概念

文件夹用来整理文件。`.py` 是 Python 源代码，`.toml` 是项目说明和依赖配置，`.json` 保存运行配置。终端（Terminal）接受文字命令。复制命令时只复制代码框中的内容，不复制提示符或说明。

本教程假设你把下载的 ZIP 放在 Mac 的“下载”文件夹。双击 ZIP 后得到 `inheco-incubator-shaker` 文件夹。不要把旧版和新版混在一起；如有同名旧文件夹，先移到其他位置。

在 Mac 按 Command + Space，搜索 Terminal，按回车打开。运行：

```bash
cd ~/Downloads/inheco-incubator-shaker
pwd
ls
```

`cd` 是进入文件夹。`~` 代表你的用户主目录。`pwd` 显示当前位置。`ls` 列出文件。应当看到 `pyproject.toml`、`src`、`tests`、`docs` 等。

如果出现 `No such file or directory`，说明文件不在这个位置。可以在终端输入 `cd `（后面一个空格），把解压后的文件夹从 Finder 拖进终端，再按回车。

## 4. 安装 Python 项目管理工具 uv

uv 会替项目准备独立的 Python 环境、安装依赖并运行命令。独立环境就是只给本项目使用的工具箱，通常放在 `.venv` 文件夹，避免影响其他项目。

先检查是否已经安装：

```bash
uv --version
```

如果显示版本号，继续下一步。如果提示 `command not found`，可从 uv 官方安装说明选择 macOS 安装方式：

https://docs.astral.sh/uv/getting-started/installation/

如果你的 Mac 已有 Homebrew，也可执行：

```bash
brew install uv
```

Homebrew 是 Mac 常见的软件包管理器；如果没有它，不必为了本教程特意安装，使用 uv 官方方法即可。安装后重新打开终端，回到项目文件夹，重新检查 `uv --version`。

这些命令会安装到你的 Mac。本次开发是在独立开发环境完成的，尚未替你在 Mac 上安装软件。

## 5. 建立环境和安装项目

在项目文件夹运行：

```bash
uv sync --python 3.12 --extra test
```

这条命令的意思是：

- `uv sync`：按项目文件和锁文件准备所需软件。
- `--python 3.12`：选用 Python 3.12，避免初学者面对多个版本。
- `--extra test`：同时安装测试工具。

首次运行需要联网。uv 可能下载 Python，创建 `.venv` 并安装项目。后续运行通常会复用这些内容。不需要手动激活 `.venv`，后面的 `uv run` 会自动使用它。

项目的关键依赖是 `unitelabs-cdk==0.16.0` 和 `pyserial==3.5`。前者提供 SiLA2 服务，后者让 Python 访问串口。项目中的 `uv.lock` 进一步记录依赖解析结果；它不代表已经在所有操作系统上测试。

完成后运行：

```bash
uv run python --version
uv run pytest -q
```

应当显示 Python 3.12 的版本，以及测试通过的结果。测试失败时先保存错误内容；此时不要切换到真实硬件模式。

## 6. 生成配置文件

运行：

```bash
uv run config create --app unitelabs.inheco_incubator_shaker:create_app
```

这会生成 `config.json`。`--app` 指出 CDK 要加载哪个 Python 模块和哪个创建函数。

拆开看：`unitelabs.inheco_incubator_shaker` 是包的导入路径，冒号后的 `create_app` 是创建服务的函数名。

配置文件相当于“这一次服务在哪里运行、连接哪台机器”的登记表。代码是通用的，配置是本次使用的选择。不要通过修改 Python 代码来更换 USB 端口。

默认配置使用模拟模式，监听 `127.0.0.1:50052`。`127.0.0.1` 指你这台 Mac 自己，50052 是服务端口。它与 `/dev/cu.usbserial-...` 这种 USB 串口路径不是同一个概念。

想明确恢复模拟模式，运行：

```bash
uv run python -m unitelabs.inheco_incubator_shaker.tools configure --simulation
```

这个小工具只修改配置，不发送硬件命令，并把修改前的配置备份到 `config.json.bak`。不要同时启动两个使用同一网络端口的服务。

## 7. 不用机器，启动模拟服务

运行：

```bash
uv run connector start --app unitelabs.inheco_incubator_shaker:create_app
```

看到 Server bound 或类似服务启动信息，表示网络服务已开始监听。终端会一直被服务占用，这是正常现象，不是死机。

保持这个窗口打开，再按 Command + N 新建终端窗口。在第二个窗口重新进入项目文件夹：

```bash
cd ~/Downloads/inheco-incubator-shaker
uv run python scripts/client_demo.py
```

这个客户端会连到第一个窗口的服务，读取 Simulation 和每层的状态。应看到 `Simulation=True`、`SIM-` 开头的模拟身份以及 JSON 状态。

JSON 可以看成“字段名和字段值组成的表”。例如 `"shaker_status": 0` 表示振荡处于关闭状态，`"temperature_c": 25.0` 是设备模拟传感器的值。

这一步已经走过真实的 SiLA/gRPC 网络调用，只是底层设备是模拟器。它不是直接跳过网络调用 Python 函数。

## 8. 完整走一次模拟操作

第二个窗口运行：

```bash
uv run python scripts/client_demo.py --demo
```

程序会：初始化第 0 层、设置振荡参数、开始振荡、停止振荡、打开抽屉、关闭抽屉，最后读取状态。`--demo` 在 Simulation=False 时会拒绝运行，防止误把学习演示变成实机动作。

模拟器不会真的加热，也不会预测物理振动。其温度保持 25°C，所以等待目标 37°C 会超时；这是预期行为，不能用它判断设备升温速度。

结束服务时，在第一个窗口按 Control + C。停止服务只是关闭通信，不能当成真实设备的急停。真实设备断开电脑后是否继续加热或振荡，需要现场核实；本项目不会在退出时偷偷发送停止或初始化命令。

## 9. 可选：用 SiLA Browser 看图形界面

SiLA Browser 是能够列出 SiLA2 功能并执行命令的客户端。安装入口在 UniteLabs 的安装页中：

https://docs.unitelabs.io/connector-development/getting-started/installation/

不同 Browser 版本的安装和界面可能不同，因此本工程也提供前面已经验证的 Python 客户端，不把学习流程绑定到某个界面版本。

如果 Browser 支持手动添加服务，使用主机 `127.0.0.1`、端口 `50052`，本地默认配置不启用 TLS。自动发现受网络和 mDNS 支持影响，列表里没有设备不等于服务未启动。开发环境中自动发现未验收，优先按地址直连。

找到 ShakerController 后，先读 Simulation，再尝试 ReadStatus。操作命令的完整列表在 `docs/API.md`。

## 10. 从模板到项目：每个文件负责什么

| 文件 | 作用 | 初学者可以怎样理解 |
|---|---|---|
| `pyproject.toml` | 名称、版本、依赖、打包方式 | 项目的身份证和购物清单 |
| `uv.lock` | 记录依赖解析版本 | 固定一份工具清单 |
| `config.py` | 声明允许哪些配置项 | 配置表的空白模板 |
| `config.json` | 当前使用的配置值 | 已填好的配置表 |
| `__init__.py` | 创建总线、协议和服务并管理生命周期 | 装配入口 |
| `features/shaker_controller.py` | 声明对外的 SiLA2 属性和命令 | 用户能看到的操作菜单 |
| `io/protocol.py` | 检查状态、执行流程、等待回读结果 | 决定按什么顺序操作 |
| `io/serial_bus.py` | 独占串口、发送并等待一条响应 | 排队收发的通信员 |
| `io/wire.py` | 打包地址和 CRC、解析返回字节 | 按厂家格式写信、拆信 |
| `io/simulator.py` | 用内存状态模拟厂家命令 | 不接设备的替身 |
| `io/errors.py` | 定义错误类别 | 分类清晰的故障说明 |
| `tools.py` | 列端口、改配置、只读探测 | 本地准备工具 |
| `scripts/client_demo.py` | 经 SiLA 网络读取和模拟演示 | 外部使用者的示例 |
| `tests/` | 自动验证接口和通信逻辑 | 回归检查清单 |

我们参考 UniteLabs Connector Factory 的目录和 CDK API，选择独立实现设备协议。不是必须安装 Omnibus，也不需要 GitLab 私有包凭据。这里“USB”采用的是虚拟串口，不是直接操作 USB 原始端点。

## 11. 假如从空项目开始，实际构建顺序是什么

第一步先确认型号。不同 shaker 的控制协议不能混用。照片铭牌给出了本项目的目标设备，但固件版本仍要实际读取。

第二步找厂家协议。我们使用 INHECO 的 FCS 900334-002，V1.5，August 2024，作为报文和命令依据。你不需要逐页读完才能运行项目，但开发者必须知道每个命令的参数、单位、返回和副作用。

第三步搭 Python 工程，写 `pyproject.toml`，建立 `src/unitelabs/inheco_incubator_shaker` 包。本工程已经完成，不需要初学者重新敲一遍全部源码。

第四步先写 `wire.py`，把“楼层 + 命令”转成字节，验证 CRC 与厂家给的示例一致。如果这里错了，上面的业务代码再正确也无法通信。

第五步写串口层。只允许一条请求处于等待回复的状态，不让三层设备同时把请求塞进同一条链路。读取时考虑分包：一次 read 不一定收到完整响应。请求有超时时间，不无限等待。超时后不自动重发动作，因为第一次动作可能已经执行。

第六步写模拟器，用相同的命令名字返回虚拟状态。这样上层协议和接口可以在没有设备时继续开发。

第七步写业务层。例如 open_drawer 不是一个字符串替换，而是检查初始化状态、检查振荡完全停止、发送开抽屉命令、读回抽屉状态。每层有自己的操作锁，整个 USB 栈另有共享通信锁。

第八步写 SiLA Feature，把业务方法公开成命令。参数写清楚类型和单位；通过装饰器交给 CDK 生成接口定义。只读无参数信息用 Property，需要指定 Address 的读取用 Command，因为 SiLA Property 不接受参数。

第九步写 create_app，把配置、真实或模拟总线、业务层和 SiLA Feature 装配起来。启动只读身份，初始化由用户明确调用。

第十步写测试，至少覆盖无效参数、不同楼层隔离、分包、错误码、超时、取消请求、网络调用。通过后再做首次真机验收。

## 12. 读懂一小段 Python

看业务层开抽屉的简化逻辑：

```python
async def drawer(self, floor, opened):
    self.check(floor)
    async with self.locks[floor]:
        await self.ready(floor)
        if await self.integer(floor, 'RSE') != 0:
            raise DeviceInterlockError('Wait until shaker is fully stopped')
        await self.bus.query(floor, 'AOD' if opened else 'ACD')
        await self.wait_value(floor, 'RDS', int(opened))
```

- `def` 声明一个函数；函数是有名字、可以反复调用的一组步骤。
- `async def` 表示这个函数会等待外部结果，在等待期间允许程序处理其他事情。
- `self` 是当前这个控制对象，`floor` 是设备楼层，`opened` 是打开还是关闭的布尔值。
- `async with ...` 在操作期间占用该楼层的锁。锁确保同一层两个相互冲突的操作不交错。
- `await` 是等待异步操作完成，不是随便停固定几秒。
- `if` 是条件判断，`!=` 表示不等于。
- `raise` 报告错误并停止这次操作；上层客户端会收到失败。
- `'AOD' if opened else 'ACD'` 在两个命令中选择一个。
- 最后一行不是再次发送动作，而是读取状态直到满足目标或超时。

SiLA 层的 `@sila.ObservableCommand(...)` 是装饰器：给普通 Python 方法增加对外网络命令的身份。`address: int` 说明 Address 必须是整数。`-> None` 说明成功时没有额外返回值，不表示没有执行。

Observable 的作用是让客户端追踪一个可能耗时的执行；它不自动实现设备进度。WaitForTemperature 额外发送测得温度作为中间结果。

## 13. 地址和单位：最容易混淆的两件事

配置里有两个不同地址：

- `master_id`：USB 所连主控背后 DIP 开关的设备 ID。需要现场核对，不能把手写数字当成它。
- `addresses`：栈内楼层，最底层通常是 0，其上是 1、2。照片上的手写 0/1/2 与此一致，但还需要读身份确认。

每层回复可能使用该层自己的 DIP ID，`reply_device_ids` 按 addresses 的顺序逐项配置。空列表时使用 master_id 作为默认预期；这只是默认策略，若实际从设备 ID 不同就必须填写实际值，不能忽略地址校验。

本接口使用 Hz、mm、°C，避免对双轴运动强行用“转速”表达。若仅作理解，10 Hz 对应每分钟 600 次周期，但本版本 ConfigureShaking 直接填写 FrequencyHz=10.0，不填 600。它设置 X/Y 相同频率和振幅；非对称或复杂比例运动不在这一版操作范围。

振幅填写的是固件定义的每轴振幅，不擅自把它换算成轨道直径。必须结合设备手册及载板实际能力选择参数。

## 14. 真机空出来之后：先识别 USB

这一章现在不需要做，不要打断其他人的使用。轮到你时，先让现有控制软件释放设备串口，再把约定使用的 USB 接到 Mac，不改级联线、不改 DIP、不更新固件。

运行：

```bash
uv run python -m unitelabs.inheco_incubator_shaker.tools ports
```

这个命令只列出系统识别到的串口，不打开端口、不发送动作。找新增的 `/dev/cu.usbserial-...` 或对应设备条目。FTDI VID/PID 可以辅助识别，但很多仪器也使用 FTDI，不能只凭它判断。

如果没有新增端口，先在 Mac“系统信息 → USB”确认设备是否枚举，检查供电、数据线和 USB 转接器，再按实际芯片和 macOS 情况判断驱动；不要一上来安装不明驱动。

## 15. 填真实配置，先做只读探测

下面的端口和 ID 只是语法示例，必须替换；ID 2 不是对照片的判断。

```bash
uv run python -m unitelabs.inheco_incubator_shaker.tools configure --hardware --port /dev/cu.usbserial-EXAMPLE --master-id 2 --floors 0 1 2 --reply-ids 2 2 2
```

这只改配置。若暂时只能确认一层，可用 `--floors 0 --reply-ids 2`，不要求三层同时验收。

然后运行：

```bash
uv run python -m unitelabs.inheco_incubator_shaker.tools probe
```

probe 打开串口，读取身份和状态，随后关闭串口。它不会调用初始化，也不会开始振荡、加热或移动抽屉。核对返回的序列号是否对应铭牌；固件字符串应来自真实设备，而不是 `SIM-`。

如果出现错误码 1，只有启动身份探测的首次只读请求允许再试一次，这是处理上电后 reset 提示；其他动作不做这种静默重试。

超时或回复 ID 不匹配时，保存日志与配置，检查 master ID、各层回复 ID、接线和串口占用。不要不断点击动作重发。出现通信超时后本服务会把总线标记为不可继续使用，要先停止服务、重新连接并读状态。之前发出的动作是否执行可能未知。

## 16. 启动实机服务与首次动作验收

只读检查通过后启动服务：

```bash
uv run connector start --app unitelabs.inheco_incubator_shaker:create_app
```

另一个终端运行默认客户端只读状态：

```bash
uv run python scripts/client_demo.py
```

此时应看到 `Simulation=False`。实机动作通过 SiLA Browser 或你自己的 SiLA 客户端调用。`--demo` 不允许控制真机。

首轮建议逐项验收，不直接串成长实验：

1. ReadStatus(Address=0)，记录温度、抽屉状态、错误标志和身份。
2. 在允许操作的现场条件下执行 InitializeDevice(Address=0)。它会关闭抽屉并停止加热与振荡，并非无副作用“连接”命令。
3. OpenDrawer → 观察实际打开 → CloseDrawer → 观察实际关闭，核对 ReadStatus。
4. 放置符合要求的载板。ConfigureShaking 选择经手册和现场确认的参数，再 StartShaking、StopShaking，确认状态与实际动作一致。
5. SetTargetTemperature → EnableHeating → 观察温度变化 → WaitForTemperature → DisableHeating，核对等待和停止行为。目标温度应由现场人员按实验条件选择。
6. 分别核对其他楼层的命令没有影响错层设备。
7. 在无在途实验的条件下验收断开、重连与恢复操作。不要直接在样品运行中拔线作为第一次故障测试。

软件范围检查不是所有机械与实验条件的替代。振幅、载板、堆叠和频率组合是否适合你的实验，需要真机验收。

## 17. 各种失败应该怎样理解

| 现象 | 意义 | 下一步 |
|---|---|---|
| `uv: command not found` | uv 没安装或终端 PATH 未更新 | 安装后重开终端 |
| 找不到 `pyproject.toml` | 当前不在项目目录 | 用 pwd、cd 确认 |
| 连接 127.0.0.1:50052 失败 | 服务未启动、端口不一致或被占用 | 看服务窗口与 config.json |
| 端口已被占用 | 另一个程序正在监听 | 停止旧服务或修改网络端口 |
| USB 串口打开失败 | 路径不对或其他软件占用 | 列端口并释放现有软件 |
| 回复 ID 不匹配 | master/floor 回复地址配置不符，或残留异常数据 | 停止、核对，不跳过检查 |
| 初始化错误 / 未初始化 | 设备尚未准备接受控制 | 现场确认后显式初始化 |
| 设备有 REF 标志 | 设备报告警告或错误 | 保存原始标志，按厂家资料处理 |
| Temperature wait timed out | 没在给定时间内满足温度条件 | 加热状态不被自动改变，检查实际情况 |
| 通信超时 / outcome unknown | 无法证明动作成功或未执行 | 停止继续调用，现场读状态后再恢复 |

本版本对任何非零 REF 标志均阻止新的正常动作（停止振荡和关闭加热仍提供入口）。这是偏保守的应用策略；不会自动清除设备错误。

厂家还描述了多层振荡时，单层停止可能因整栈振动而迟迟不完成的情况。本版没有验证广播停止或提供软件急停保证；StopShaking 超时会让总线退出可继续发送状态。验收时应专门测试你的堆叠停止行为，并按照厂家建议和现场流程处理。不要把重试 StopShaking 当成一定可靠的补救。

## 18. 这份测试结果证明了什么

本项目自动测试覆盖：

- 厂家示例报文的 CRC 对照；
- 分片回复、错误码、异常地址、额外换行、报文长度；
- 多楼层状态隔离、互锁、参数范围、读回确认；
- 初始化、振荡、温控和温度等待的模拟流程；
- 超时后拒绝继续发送、不自动重试写操作；
- 调用者取消请求后，仍等待底层收发线程结束才释放总线；
- 真正的 SiLA/gRPC 客户端与服务端往返；
- 通过操作系统伪终端运行 pyserial，验证串口收发路径。

没有覆盖：你的 Mac 驱动、这三台实物的固件差异、回复 ID 实际值、载板检测、温度准确性、机械稳定性、局域网自动发现、真实堆叠停止行为。伪终端和模拟器都不是设备数字孪生。

这些边界记录在 VALIDATION.md。只有在真机验收后，才适合把状态改成“已在该型号与固件上验证”。

## 19. 以后怎样继续维护

修改代码后先运行 `uv run pytest -q`。失败时先定位是打包、协议、业务逻辑还是网络接口层，不直接带着失败测试接设备。

不要在日志里只写“失败”。要保留时间、楼层、命令、返回错误和配置。调试真实协议时可临时启用 Python logging 的 DEBUG 级别，serial_bus 会记录 TX/RX 的十六进制字节；配置和日志不打进发布包。

升级依赖后重新生成锁文件并验证，而不是只改版本号。新增一种设备型号需要明确能力和测试，不能仅因为厂商相同就放宽 RTS 检查。

后续若要长时间无人值守，还需要现场确认断线后的行为、持久化操作记录、恢复策略及部署监控。当前工程提供基础操作接口，并未宣称经过长期生产运行验证。

## 20. 原始资料

- UniteLabs 安装与项目创建：https://docs.unitelabs.io/connector-development/getting-started/installation/
- UniteLabs 项目结构：https://docs.unitelabs.io/connector-development/guides/project-structure/
- UniteLabs 控制命令：https://docs.unitelabs.io/connector-development/tutorial/controls/
- Connector Factory：https://gitlab.com/unitelabs/cdk/connector-factory
- INHECO 支持页及手册下载：https://www.inheco.com/single-plate-incubator-shaker-support.html
- INHECO FCS 900334-002 v1.5：https://www.inheco.com/data/pdf/single-plate-incubators-firmware-command-202408-0522-1050-58.pdf
- uv 安装：https://docs.astral.sh/uv/getting-started/installation/

所有示例主机路径、DIP ID 和实验参数都需要结合实际使用环境确认。本次开发没有向任何物理设备发送命令。
