# 运行与资源

配置有效值沿 core/app_settings.py 的 effective 链，页面库值与 .env 职责见 [部署](../guides/deployment.md)。PDF 使用 headless Chromium，服务账户必须能访问浏览器及字体；render.py 为避挂死保留的回收方式在改变生命周期前要核实际服务环境。打印版式来自 i8，IPP 接收不等于纸面完成。

共享Excel读表与单元格解析保留在import_kit/workbook、readers、parse；通用API/域映射向导及旧两域专属编排已退出，既有模型及历史批次/来源读取保持。机械费的网页JSON导入、明细汇总确认和一次性历史接续写入链已退出；历史参考继续供累计计算。mod06_proc/mech_report的只读报表解析仍用于真实导出回读验证；模板生成及透视缓存回 [模板](../reference/template-export.md)。真实资产由 report_export/resources.py 和文件字节定义，delivery 只作第三方来源，不能反推业务。有效分层、隔离、金额、撤销及模板测试保留；已退出文档机器链不再影响运行配置。

过程资料的库存读取仍经mod08数据主人；`load_process_rows`只投影所需九列并附同一调整痕迹，保原金额Decimal、ID行序和两次批量查询。普通库存规范行、原单/调整单及其他消费者保持原出口。库存扩展调整保存在旁路JSON中，旧amount-only记录原样兼容；core.money负责最终联算与舍入，React使用Decimal.js只预览。保存/撤销在原单行锁下验证源值与当前调整令牌，不修改导入原字段；调整后物料性质用于过程归类，多字段差异留痕随同一批量投影读取。
