#!/usr/bin/env python3
from pathlib import Path


def replace(path, old, new):
    file = Path(path)
    text = file.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"Unsupported Mesa source: {path}: {old!r}")
    file.write_text(text.replace(old, new, 1))


kgsl = 'src/freedreno/vulkan/tu_knl_kgsl.cc'
device = 'src/freedreno/vulkan/tu_device.cc'
replace(kgsl, '#include <sys/mman.h>', '#include <sys/mman.h>\n#include <sys/stat.h>\n#include <sys/sysmacros.h>')
replace(kgsl, '   result = tu_physical_device_init(device, instance);', '''   struct stat kgsl_st;
   if (fstat(fd, &kgsl_st) == 0 && S_ISCHR(kgsl_st.st_mode)) {
      device->has_local = device->has_master = true;
      device->local_major = device->master_major = major(kgsl_st.st_rdev);
      device->local_minor = device->master_minor = minor(kgsl_st.st_rdev);
   }

   result = tu_physical_device_init(device, instance);''')
replace(device, '.EXT_physical_device_drm = !is_kgsl(device->instance),', '.EXT_physical_device_drm = !is_kgsl(device->instance) || device->has_local,')
text = Path(kgsl).read_text()
function = 'static int\nkgsl_device_get_gpu_timestamp(struct tu_device *dev, uint64_t *ts)\n{\n   UNREACHABLE("");\n   return 0;\n}\n\n'
if function not in text:
    raise SystemExit('KGSL timestamp implementation changed; review before building')
text = text.replace(function, '').replace('      .device_get_gpu_timestamp = kgsl_device_get_gpu_timestamp,\n', '')
Path(kgsl).write_text(text)
replace('src/freedreno/vulkan/tu_knl.cc', '   return dev->instance->knl->device_get_gpu_timestamp(dev, ts);', '''   if (dev->instance->knl->device_get_gpu_timestamp == NULL)
      return -1;
   return dev->instance->knl->device_get_gpu_timestamp(dev, ts);''')
for extension in ('KHR_calibrated_timestamps', 'EXT_calibrated_timestamps', 'EXT_present_timing'):
    replace(device, f'.{extension} = device->info->props.has_persistent_counter,', f'.{extension} = device->info->props.has_persistent_counter && device->instance->knl->device_get_gpu_timestamp != NULL,')
for feature in ('presentTiming', 'presentAtRelativeTime', 'presentAtAbsoluteTime'):
    replace(device, f'features->{feature} = true;', f'features->{feature} = pdevice->vk.supported_extensions.EXT_present_timing;')
print('Linux KGSL Wayland and timestamp fixes verified')
