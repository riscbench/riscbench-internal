# 2026-07-31T15:15:22.543189100
import vitis

client = vitis.create_client()
client.set_workspace(path="mig")

platform = client.get_component(name="platform")
status = platform.update_hw(hw_design = "$COMPONENT_LOCATION/../../../Vivado/MIIGTEST/design_1_wrapper.xsa")

status = platform.build()

status = platform.build()

comp = client.get_component(name="hello_world")
comp.build()

status = platform.build()

comp.build()

status = platform.build()

comp.build()

comp = client.get_component(name="hello_world")
comp.set_app_config(key = "USER_COMPILE_OTHER_FLAGS", values = ["-mcmodel=medany"])

status = platform.build()

comp = client.get_component(name="hello_world")
comp.build()

comp = client.get_component(name="hello_world")
comp.set_app_config(key = "USER_COMPILE_OTHER_FLAGS", values = [""])

comp.set_app_config(key = "USER_COMPILE_OTHER_FLAGS", values = ["-mcmodel=medany"])

comp.set_app_config(key = "USER_LINK_OTHER_FLAGS", values = ["-mcmodel=medany"])

status = platform.build()

comp = client.get_component(name="hello_world")
comp.build()

component = client.get_component(name="hello_world")

lscript = component.get_ld_script(path="C:\Users\projj\Vitis\mig\hello_world\src\lscript.ld")

lscript.set_stack_size("0x200")

lscript.set_heap_size("0x0")

status = platform.build()

comp.build()

status = platform.build()

comp.build()

status = platform.build()

comp.build()

status = platform.build()

comp.build()

status = platform.build()

comp.build()

vitis.dispose()

