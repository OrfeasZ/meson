# Copyright 2014-2016 The Meson development team

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import xml.etree.ElementTree as ET

from .vs2010backend import Vs2010Backend
from .ninjabackend import NinjaBackend


class VsHybridBackend(Vs2010Backend):
    def __init__(self, build):
        super().__init__(build)
        self.name = 'vshybrid'
        self.platform_toolset = 'v141'
        self.vs_version = '2017'

        # WindowsSDKVersion should be set by command prompt.
        sdk_version = os.environ.get('WindowsSDKVersion', None)

        if sdk_version:
            self.windows_target_platform_version = sdk_version.rstrip('\\')

        # Create an instance of the ninja backend internally
        self.ninja_gen = NinjaBackend(build)

    def generate(self, interp):
        # Generate ninja configuration files.
        self.ninja_gen.generate(interp)

        # Generate hybrid VS project files.
        super().generate(interp)

    def generate_debug_information(self, link):
        # valid values for vs2017 is 'false', 'true', 'DebugFastLink', 'DebugFull'
        ET.SubElement(link, 'GenerateDebugInformation').text = 'DebugFull'

    def gen_vcxproj_includes(self, root, down, target, headers, gen_hdrs, extra_files):
        if len(headers) + len(gen_hdrs) + len(extra_files) == 0:
            return

        inc_hdrs = ET.SubElement(root, 'ItemGroup')

        for h in headers:
            relpath = os.path.join(down, h.rel_to_builddir(self.build_to_src))
            ET.SubElement(inc_hdrs, 'None', Include=relpath)
        for h in gen_hdrs:
            ET.SubElement(inc_hdrs, 'None', Include=h)
        for h in extra_files:
            relpath = os.path.join(down, h.rel_to_builddir(self.build_to_src))
            ET.SubElement(inc_hdrs, 'None', Include=relpath)

    def gen_vcxproj_compile(self, root, down, target, file_args, file_defines, file_inc_dirs, proj_to_src_dir, sources, gen_src, pch_sources):
        if len(sources) + len(gen_src) + len(pch_sources) == 0:
            return

        inc_src = ET.SubElement(root, 'ItemGroup')
        for s in sources:
            relpath = os.path.join(down, s.rel_to_builddir(self.build_to_src))
            inc_cl = ET.SubElement(inc_src, 'CustomBuild', Include=relpath)

            obj_basename = self.ninja_gen.object_filename_from_source(target, s)
            rel_obj = os.path.join(target.get_subdir(), target.get_id(), obj_basename)

            ET.SubElement(inc_cl, 'Command').text = "call ninja -C %s %s" % (down, rel_obj)
            ET.SubElement(inc_cl, 'Outputs').text = "%s" % os.path.join(down, rel_obj)

        # TODO: Support generated sources
        # TODO: Support precompiled headers

    def gen_vcxproj_footer(self, root, down, target):
        super().gen_vcxproj_footer(root, down, target)

        cmd_base = 'call ninja -C %s ' % down

        build = ET.SubElement(root, 'Target', Name='Build')
        ET.SubElement(build, 'Exec', Command=(cmd_base
                                              + os.path.join(target.get_subdir(), target.get_filename())))

        clean = ET.SubElement(root, 'Target', Name='Clean')
        ET.SubElement(clean, 'Exec', Command=(cmd_base + '-tclean '
                                              + os.path.join(target.get_subdir(), target.get_filename())))

    def gen_vcxproj_clconfig(self, root, down, target, clconf, file_inc_dirs, target_inc_dirs,
                             file_defines, target_defines, target_args, proj_to_src_dir, compiler):
        includes = target_inc_dirs

        for lang in file_inc_dirs:
            for inc_dir in file_inc_dirs[lang]:
                if inc_dir not in includes:
                    includes.append(inc_dir)

        defines = target_defines

        for lang in file_defines:
            for define in file_defines[lang]:
                if define not in defines:
                    defines.append(define)

        if len(target_args) > 0:
            target_args.append('%(AdditionalOptions)')
            ET.SubElement(clconf, "AdditionalOptions").text = ' '.join(target_args)

        target_inc_dirs.append('%(AdditionalIncludeDirectories)')
        ET.SubElement(clconf, 'AdditionalIncludeDirectories').text = ';'.join(includes)
        target_defines.append('%(PreprocessorDefinitions)')
        ET.SubElement(clconf, 'PreprocessorDefinitions').text = ';'.join(defines)
        ET.SubElement(clconf, 'MinimalRebuild').text = 'true'
        ET.SubElement(clconf, 'FunctionLevelLinking').text = 'true'

        # Warning level
        warning_level = self.get_option_for_target('warning_level', target)
        ET.SubElement(clconf, 'WarningLevel').text = 'Level' + str(1 + int(warning_level))
        if self.get_option_for_target('werror', target):
            ET.SubElement(clconf, 'TreatWarningAsError').text = 'true'

    def get_target_deps(self, t, recursive=False):
        return {}
