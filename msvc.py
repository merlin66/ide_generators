#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Utilities for generating project files for Microsoft Visual Studio"""

#
# Copyright (c) 2011 Thomas Berg
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import codecs
import hashlib
import ntpath
import os
import sys

import xml.etree.cElementTree as ET
from xml.dom import minidom

# From SCons
external_makefile_guid = '{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}'

# Version numbers and cl.exe version numbers:
# Visual Studio 2005  8.0 14.00
# Visual Studio 2008  9.0 15.00
# Visual Studio 2010 10.0 16.00
# Visual Studio 2012 11.0 17.00
# Visual Studio 2013 12.0 18.00
# Visual Studio 2015 14.0 19.00
# Visual Studio 2017 15.0 19.10

sln_headers = {
    8.0  : "Microsoft Visual Studio Solution File, Format Version 9.00\n# Visual Studio 2005\n",
    9.0  : "Microsoft Visual Studio Solution File, Format Version 10.00\n# Visual Studio 2008\n",
    10.0 : "Microsoft Visual Studio Solution File, Format Version 11.00\n# Visual Studio 2010\n",
    11.0 : "Microsoft Visual Studio Solution File, Format Version 12.00\n# Visual Studio 2012\n",
    12.0 : "Microsoft Visual Studio Solution File, Format Version 12.00\n# Visual Studio 2013\n",
    14.0 : "Microsoft Visual Studio Solution File, Format Version 12.00\n# Visual Studio 2015\n",
    15.0 : "Microsoft Visual Studio Solution File, Format Version 12.00\n# Visual Studio 2017\n",
}

configuration_types = {
    'Makefile'       : 0,
    'Application'    : 1,
    'DynamicLibrary' : 2,
    'StaticLibrary'  : 4,
    'Utility'        : 10,
}

project_property_map = {
    'Makefile'                   : 'make_properties',
}

tools_map_vc8 = {
    'make_properties' : 'VCNMakeTool',
}

tools_reverse_map_vc8 = {}
for k in tools_map_vc8.keys():
    tools_reverse_map_vc8[tools_map_vc8[k]] = k

properties_map_vc8 = {
    'build_command_line'         : 'BuildCommandLine',
    'clean_command_line'         : 'CleanCommandLine',
    'rebuild_command_line'       : 'RebuildCommandLine',
    'output'                     : 'Output',
    'preprocessor_definitions'   : 'PreprocessorDefinitions',
    'include_search_path'        : 'IncludeSearchPath',
}

properties_map_vc10 = {
    'build_command_line'         : 'NMakeBuildCommandLine',
    'clean_command_line'         : 'NMakeCleanCommandLine',
    'rebuild_command_line'       : 'NMakeReBuildCommandLine',
    'output'                     : 'NMakeOutput',
    'preprocessor_definitions'   : 'NMakePreprocessorDefinitions',
    'include_search_path'        : 'NMakeIncludeSearchPath',
}

user_map_vc10 = {
    'working_directory'          : 'LocalDebuggerWorkingDirectory',
    'debugger_flavor'            : 'DebuggerFlavor',
    'debugger_command'           : 'LocalDebuggerCommand',
    'debugger_environment'       : 'LocalDebuggerEnvironment',
    'debugger_arguments'         : 'LocalDebuggerCommandArguments',
}

configuration_tools_vc8 = {
    'Makefile' : [
                "VCNMakeTool"
    ],
    'Application' : [
                "VCPreBuildEventTool",
                "VCCustomBuildTool",
                "VCXMLDataGeneratorTool",
                "VCWebServiceProxyGeneratorTool",
                "VCMIDLTool",
                "VCCLCompilerTool",
                "VCManagedResourceCompilerTool",
                "VCResourceCompilerTool",
                "VCPreLinkEventTool",
                "VCLinkerTool",
                "VCALinkTool",
                "VCManifestTool",
                "VCXDCMakeTool",
                "VCBscMakeTool",
                "VCFxCopTool",
                "VCAppVerifierTool",
                "VCPostBuildEventTool",
    ],
    'DynamicLibrary' : [
                "VCPreBuildEventTool",
                "VCCustomBuildTool",
                "VCXMLDataGeneratorTool",
                "VCWebServiceProxyGeneratorTool",
                "VCMIDLTool",
                "VCCLCompilerTool",
                "VCManagedResourceCompilerTool",
                "VCResourceCompilerTool",
                "VCPreLinkEventTool",
                "VCLinkerTool",
                "VCALinkTool",
                "VCManifestTool",
                "VCXDCMakeTool",
                "VCBscMakeTool",
                "VCFxCopTool",
                "VCAppVerifierTool",
                "VCPostBuildEventTool",
            ],
    'StaticLibrary' : [
                "VCPreBuildEventTool",
                "VCCustomBuildTool",
                "VCXMLDataGeneratorTool",
                "VCWebServiceProxyGeneratorTool",
                "VCMIDLTool",
                "VCCLCompilerTool",
                "VCManagedResourceCompilerTool",
                "VCResourceCompilerTool",
                "VCPreLinkEventTool",
                "VCLibrarianTool",
                "VCALinkTool",
                "VCXDCMakeTool",
                "VCBscMakeTool",
                "VCFxCopTool",
                "VCPostBuildEventTool",
    ],
    'Utility' : [
                "VCPreBuildEventTool",
                "VCCustomBuildTool",
                "VCMIDLTool",
                "VCPostBuildEventTool",
    ],
}

def get_toolset_version(project):
    version = project.toolset_version
    if version is None:
        version = project.version
    return 'v%s' % int(version * 10)

# From SCons
def xmlify(s):
    s = s.replace("&", "&amp;") # do this first
    s = s.replace("'", "&apos;")
    s = s.replace('"', "&quot;")
    return s

# From SCons
def _generateGUID(slnfile, name):
    """This generates a dummy GUID for the sln file to use.  It is
    based on the MD5 signatures of the sln filename plus the name of
    the project.  It basically just needs to be unique, and not
    change with each invocation."""
    m = hashlib.md5()
    # Normalize the slnfile path to a Windows path (\ separators) so
    # the generated file has a consistent GUID even if we generate
    # it on a non-Windows platform.
    m.update((ntpath.normpath(str(slnfile)) + str(name)).encode('utf-8'))
    solution = m.hexdigest().upper()
    # convert most of the signature to GUID form (discard the rest)
    solution = "{" + solution[:8] + "-" + solution[8:12] + "-" + solution[12:16] + "-" + solution[16:20] + "-" + solution[20:32] + "}"
    return solution

class Project():
    def __init__(self, filepath, archs, variants, files, project_info, name = None, src_root = None, strip_path = None, version = None, toolset_version = None):
        self.filepath = filepath
        self.archs = archs
        self.variants = variants
        self.project_info = project_info
        self.configuration_type = project_info['project_type']
        self.files = files
        self.name = name
        self.src_root = src_root
        self.strip_path = strip_path
        self.version = version
        self.toolset_version = toolset_version
        if name is None:
            self.name = os.path.splitext(os.path.split(filepath)[-1])[0]

        self.guid = _generateGUID(filepath, name)

    def get_project_info(self, entry, variant, arch):
        possible_keys = [
            '%s|%s|%s' % (entry, variant, arch),
            '%s|%s' % (entry, variant),
            '%s|%s' % (entry, arch),
            entry,
            ]
        for key in possible_keys:
            try:
                return self.project_info[key]
            except KeyError:
                pass
        return dict()

def _strip_folder(subfolder, strip_path):
    if strip_path is None:
        return subfolder
    strip_path = strip_path.replace('/', '\\') # TODO: slash consistency
    assert subfolder.startswith(strip_path)
    result = subfolder[len(strip_path)+1:]
    return result

def _add_file_nodes(parent_node, project):
    filemap = project.files
    project_path = project.filepath
    src_root = project.src_root
    strip_path = project.strip_path
    filters = { '' : parent_node } # Parent of the empty filter
    def get_filterparent(total_filter):
        assert total_filter != '/', 'Illegal input'
        if total_filter in filters:
            return filters[total_filter]
        result = os.path.split(total_filter)
        if len(result) > 1:
            parent_string = result[0]
            child_string = result[1]
        else:
            parent_string = ''
            child_string = total_filter

        parent = get_filterparent(parent_string)
        newfilter = ET.SubElement(parent, 'Filter', Name = child_string)
        filters[total_filter] = newfilter
        return newfilter

    filetype_first = True

    for f in filemap:
        type_filter = f
        for filepath in filemap[f]:
            result = os.path.split(filepath)
            subfolder = None
            if len(result) > 1:
                subfolder = result[0]
            subfolder = _strip_folder(subfolder, strip_path)
            if filetype_first:
                total_filter = type_filter
                if subfolder:
                    if total_filter:
                        total_filter += '/'
                    total_filter += subfolder
            else:
                total_filter = ''
                if subfolder:
                    total_filter += subfolder
                if type_filter:
                    if total_filter:
                        total_filter += '/'
                    total_filter += type_filter

            filterparent = get_filterparent(total_filter)
            if src_root is not None:
                filepath = os.path.join(src_root, filepath)
            filepath = filepath.replace('/', '\\')
            relative = os.path.relpath(filepath, os.path.split(project_path)[0])
            ET.SubElement(filterparent, 'File', RelativePath = relative)
    else:
        #TODO: are projects without files valid?
        pass

def generate_xml_vc8(project):
    xml_project = ET.Element('VisualStudioProject',
        ProjectType            = 'Visual C++',
        Version                = '{0:.2f}'.format(project.version),
        name                   = project.name,
        ProjectGUID            = project.guid,
        TargetFrameworkVersion = '131072'
    )

    platforms = ET.SubElement(xml_project, 'Platforms')
    for arch in project.archs:
        platform = ET.SubElement(platforms, 'Platform', Name = arch)
    toolfiles = ET.SubElement(xml_project, 'ToolFiles')

    configurations = ET.SubElement(xml_project, 'Configurations')
    for arch in project.archs:
        for variant in project.variants:
            configuration = ET.SubElement(
                configurations,
                'Configuration',
                Name = '%s|%s' % (variant, arch),
                ConfigurationType = str(configuration_types[project.configuration_type]),
                #InheritedPropertySheets=".\foo.vsprops;.\bar.vsprops;",
                UseOfMFC = "0",
                ATLMinimizesCRunTimeLibraryUsage = "false",
            )
            tools = configuration_tools_vc8[project.configuration_type]
            for tool in tools:
                try:
                    mapped_tool = tools_reverse_map_vc8[tool]
                except KeyError:
                    mapped_tool = tool
                d = project.get_project_info(mapped_tool, variant, arch)
                mapped_dict = {}
                for k in d.keys():
                    mapped_dict[properties_map_vc8[k]] = d[k]
                tool_element = ET.SubElement(configuration, 'Tool', Name = tool, **mapped_dict)

    references = ET.SubElement(xml_project, 'References')
    files = ET.SubElement(xml_project, 'Files')
    if project.files:
        _add_file_nodes(parent_node = files, project = project)

    xml_globals = ET.SubElement(xml_project, 'Globals')
    return xml_project

def get_file_groups(filemap):
    text_files = []
    header_files= []
    cl_files = []
    header_extensions = set(['.h', '.hpp', '.hxx', 'txx'])
    cl_extensions = set(['.c', '.cpp', '.cxx'])
    for key in filemap.keys():
        for file in filemap[key]:
            ext = os.path.splitext(file)[1].lower()
            if ext in cl_extensions:
                cl_files.append(file)
            elif ext in header_extensions:
                header_files.append(file)
            else:
                text_files.append(file)
    return text_files, header_files, cl_files

def generate_xml_vc10(project):
    xml_project = ET.Element('Project',
        DefaultTargets="Build",
        ToolsVersion="4.0" if project.version <= 12.0 else "14.0",
        xmlns="http://schemas.microsoft.com/developer/msbuild/2003"
    )
    # Configurations
    configurations = ET.SubElement(xml_project, 'ItemGroup', Label='ProjectConfigurations')
    for arch in project.archs:
        for variant in project.variants:
            node = ET.SubElement(configurations, 'ProjectConfiguration',
                Include='%s|%s' % (variant, arch))
            configuration = ET.SubElement(node, 'Configuration')
            configuration.text = variant
            platform = ET.SubElement(node, 'Platform')
            platform.text = arch
    # Globals
    globals = ET.SubElement(xml_project, 'PropertyGroup', Label='Globals')
    project_guid = ET.SubElement(globals, 'ProjectGuid')
    project_guid.text = project.guid
    keyword = ET.SubElement(globals, 'Keyword')
    keyword.text = 'MakeFileProj' # Hard coded
    # Default properties
    default_props = ET.SubElement(xml_project, 'Import', Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props")
    # Configuration properties
    for arch in project.archs:
        for variant in project.variants:
            pg = ET.SubElement(xml_project, 'PropertyGroup',
                Condition="'$(Configuration)|$(Platform)'=='%s|%s'" % (variant, arch),
                Label='Configuration')
            ct = ET.SubElement(pg, 'ConfigurationType')
            ct.text = 'Makefile' # Hard coded
            db = ET.SubElement(pg, 'UseDebugLibraries')
            db.text = 'false' # Hard coded
            ts = ET.SubElement(pg, 'PlatformToolset')
            ts.text = get_toolset_version(project)
    # Cpp props
    cpp_props = ET.SubElement(xml_project, 'Import', Project="$(VCTargetsPath)\Microsoft.Cpp.props")
    # ExtensionSettings
    ext_settings = ET.SubElement(xml_project, 'ImportGroup', Label='ExtensionSettings')
    # PropertySheets
    for arch in project.archs:
        for variant in project.variants:
            ig = ET.SubElement(xml_project, 'ImportGroup', Label='PropertySheets',
                Condition="'$(Configuration)|$(Platform)'=='%s|%s'" % (variant, arch))
            node = ET.SubElement(ig, 'Import', Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props",
                Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')",
                Label="LocalAppDataPlatform")
    # UserMacros
    user_macros = ET.SubElement(xml_project, 'PropertyGroup', Label='UserMacros')
    # Configuration properties
    for arch in project.archs:
        for variant in project.variants:
            pg = ET.SubElement(xml_project, 'PropertyGroup',
                Condition="'$(Configuration)|$(Platform)'=='%s|%s'" % (variant, arch))

            d = project.get_project_info('make_properties', variant, arch)
            for key in properties_map_vc10:
                toolname = properties_map_vc10[key]
                info = ET.SubElement(pg, toolname)
                info.text = d[key]
    # ItemDefinitionGroup
    idg = ET.SubElement(xml_project, 'ItemDefinitionGroup')

    filemap = project.files
    text_files, header_files, cl_files = get_file_groups(filemap)

    # Text, ClCompile and ClInclude files
    groups = {
        'None' : text_files,
        'ClCompile' : cl_files,
        'ClInclude' : header_files,
    }
    src_root = project.src_root
    project_path = project.filepath
    for g in groups.keys():
        ig = ET.SubElement(xml_project, 'ItemGroup')
        for filepath in groups[g]:
            if src_root is not None:
                filepath = os.path.join(src_root, filepath)
            filepath = filepath.replace('/', '\\')
            relative = os.path.relpath(filepath, os.path.split(project_path)[0])
            node = ET.SubElement(ig, g, Include=relative)

    # targets
    targets = ET.SubElement(xml_project, 'Import', Project="$(VCTargetsPath)\Microsoft.Cpp.targets")
    # extension targets
    targets = ET.SubElement(xml_project, 'ImportGroup', Label="ExtensionTargets")
    return xml_project

def generate_user_vc10(project):
    xml_project = ET.Element('Project',
        ToolsVersion='4.0' if project.version <= 12.0 else '14.0',
        xmlns="http://schemas.microsoft.com/developer/msbuild/2003"
    )
    # User properties
    for arch in project.archs:
        for variant in project.variants:
            d = project.get_project_info('user_properties', variant, arch)
            if d:
                pg = ET.SubElement(xml_project, 'PropertyGroup',
                Condition="'$(Configuration)|$(Platform)'=='%s|%s'" % (variant, arch))
                for key in user_map_vc10:
                    if d.get(key):
                        vc_name = user_map_vc10[key]
                        info = ET.SubElement(pg, vc_name)
                        info.text = d[key]
    return xml_project

def generate_filters_vc10(project):
    xml_project = ET.Element('Project', ToolsVersion="4.0", xmlns="http://schemas.microsoft.com/developer/msbuild/2003")

    filemap = project.files
    project_path = project.filepath
    src_root = project.src_root
    strip_path = project.strip_path

    text_files, header_files, cl_files = get_file_groups(filemap)

    filter_map = {}
    filters = set()
    for f in filemap:
        type_filter = f
        for filepath in filemap[f]:
            result = os.path.split(filepath)
            subfolder = None
            if len(result) > 1:
                subfolder = result[0]
            subfolder = _strip_folder(subfolder, strip_path)
            filetype_first = True
            if filetype_first:
                total_filter = type_filter
                if subfolder:
                    if total_filter:
                        total_filter += '/'
                    total_filter += subfolder
            else:
                total_filter = ''
                if subfolder:
                    total_filter += subfolder
                if type_filter:
                    if total_filter:
                        total_filter += '/'
                    total_filter += type_filter
            total_filter = total_filter.replace('/', '\\')
            filter_map[filepath] = total_filter
            filters.add(total_filter)

            # If a filter 'foo\bar\chi' exists, we also have to make sure
            # the filters 'foo' and  'foo\bar' exists. So generate any
            # missing filters:
            components = total_filter.split('\\')
            for i in range(1, len(components)):
                subfilter = '\\'.join(components[0:i])
                filters.add(subfilter)

    # First define the set of filters (can list the extensions for each filter)
    ig = ET.SubElement(xml_project, 'ItemGroup')
    for filter in sorted(filters):
        if filter == '':
            continue
        fn = ET.SubElement(ig, 'Filter', Include = filter)
        uid = ET.SubElement(fn, 'UniqueIdentifier')
        uid.text = _generateGUID(project.filepath, filter)

    groups = {
        'None' : text_files,
        'ClCompile' : cl_files,
        'ClInclude' : header_files,
    }

    for g in groups.keys():
        ig = ET.SubElement(xml_project, 'ItemGroup')
        for filepath in groups[g]:
            filter = filter_map[filepath]
            if src_root is not None:
                filepath = os.path.join(src_root, filepath)
            filepath = filepath.replace('/', '\\')
            relative = os.path.relpath(filepath, os.path.split(project_path)[0])
            node = ET.SubElement(ig, g, Include=relative)
            if filter:
                fn = ET.SubElement(node, 'Filter')
                fn.text = filter

    return xml_project

def write_xml(xml, filepath, encoding, pretty):
    if pretty:
        s = ET.tostring(xml)
        with codecs.open(filepath, 'w', encoding = encoding) as out:
            out.write(minidom.parseString(s).toprettyxml(encoding = encoding))
    else:
        doc = ET.ElementTree(xml)

        if sys.version_info < (3, 0):
            with codecs.open(filepath, 'w', encoding = encoding) as out:
                # Manually adds utf8 tag, then uses doc.write.
                out.write('<?xml version="1.0" encoding="%s"?>\n' % encoding)
                doc.write(out, encoding = encoding)
        else:
            # doc.write doesn't work with python 3 due to some weird interference
            # with scons and file writing.
            # This leaves out the encoding tag.
            doc.write(filepath, encoding = encoding)

def write_project(project, filepath):
    encoding = 'utf-8'
    pretty = True

    if project.version <= 9.0:
        xml_project = generate_xml_vc8(project)
        xml_filters = None
        xml_user = None
    else:
        xml_project = generate_xml_vc10(project)
        xml_filters = generate_filters_vc10(project)
        xml_user    = generate_user_vc10(project)

    # == write resulting xml ==
    write_xml(xml_project, filepath, encoding, pretty)
    if xml_filters:
        write_xml(xml_filters, filepath + '.filters', encoding, pretty)
    if xml_user:
        write_xml(xml_user, filepath + '.user', encoding, pretty)

def write_solution(version, projects, variants, archs, dependencies, out, solution_items = None):
    out.write(sln_headers[version])
    for project in projects:
        filepath = project.filepath
        guid = project.guid
        name = project.name
        out.write('Project("%s") = "%s", "%s", "%s"\n' % ( external_makefile_guid, name, filepath.replace('/', '\\'), guid ))
        deps = dependencies.get(project)
        if deps:
            out.write('\tProjectSection(ProjectDependencies) = postProject\n')
            for dep in deps:
                guid = dep.guid
                out.write('%s = %s\n' % (guid, guid))
            out.write('\tEndProjectSection')
        out.write('EndProject\n')

    if (version > 10) and solution_items:
        out.write('Project("%s") = "%s", "%s", "%s"\n' % ('{2150E333-8FDC-42A3-9474-1A3956D46DE8}', 'Solution Items',
                                                          'Solution Items', guid))
        out.write('\tProjectSection(SolutionItems) = preProject\n')
        for item in solution_items:
            out.write('\t\t%s\n' % item)
        out.write('\tEndProjectSection\n')
        out.write('EndProject\n')

    out.write('Global\n')
    out.write('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n')
    for variant in variants:
        for arch in archs:
            out.write('\t\t%s|%s = %s|%s\n' % (variant, arch, variant, arch))
    out.write('\tEndGlobalSection\n')

    out.write('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n')
    for variant in variants:
        for arch in archs:
            for p in projects:
                filepath = p.filepath
                guid = p.guid
                for s in ['\t\t%s.%s|%s.ActiveCfg = %s|%s\n', '\t\t%s.%s|%s.Build.0 = %s|%s\n']:
                    out.write(s % (guid,variant,arch,variant,arch))
    out.write('\tEndGlobalSection\n')

    out.write('\tGlobalSection(SolutionProperties) = preSolution\n')
    out.write('\t\tHideSolutionNode = FALSE\n')
    out.write('\tEndGlobalSection\n')

    out.write('EndGlobal\n')


#====== Code for testing ======
def _get_test_projects(variants, archs, version, toolset_version):
    ext = 'vcproj' if version <= 9.0 else 'vcxproj'
    project_files = [
        'test.%s' % ext,
        'testfolder/test2.%s' % ext,
    ]
    files = {
        'src'     : ['testfolder/main.cpp'],
        'misc'    : [
                     'testfolder/SConscript',
                     'SConstruct'
                     ],
        ''         : ['README.txt']
    }

    project_info = {
        'project_type' : 'Makefile',

        'make_properties|Win32' : dict(
            build_command_line="scons.bat",
            clean_command_line="scons.bat -c",
            rebuild_command_line="scons.bat -c && scons.bat",
            output="foo.exe",
            preprocessor_definitions="FOO;BAR",
            include_search_path="C:/foo",
            ),
        'make_properties|x64' : dict(
            build_command_line="scons.bat",
            clean_command_line="scons.bat -c",
            rebuild_command_line="scons.bat -c && scons.bat",
            output="foo.exe",
            preprocessor_definitions="FOO;BAR",
            include_search_path="C:/foo",
            ),
    }

    projects = [ Project(filepath = p,
                         variants = variants,
                         archs = archs,
                         files = files,
                         version = version,
                         toolset_version = toolset_version,
                         project_info = project_info,
                         ) for p in project_files ]

    dependencies = {
        projects[1] : [projects[0]]
    }
    return projects, dependencies

def _prepare_dirs(filepath):
    d = os.path.split(filepath)[0]
    if not os.path.exists(d):
        os.makedirs(d)

def _make_test_files(testroot, projects):
    for p in projects:
        for key in p.files:
            for f in p.files[key]:
                filepath = os.path.join(testroot, f)
                _prepare_dirs(filepath)
                out = open(filepath, 'w')
                out.write('\n')
                out.close()

def test():
    variants = ['Debug', 'Release']
    archs = ['Win32', 'x64']
    version = 15.0
    toolset_version = 14.2
    sln_name = 'testsolution.sln'
    projects, dependencies = _get_test_projects(variants, archs, version, toolset_version)

    testroot = 'temp'
    _make_test_files(testroot, projects)

    out = open(os.path.join(testroot, sln_name), 'w')
    write_solution(version = version,
                   projects = projects,
                   variants = variants,
                   archs = archs,
                   dependencies = dependencies,
                   out = out)
    out.close()
    print('Created %s' % sln_name)

    for project in projects:
        write_project(project = project,
                      filepath = os.path.join(testroot, project.filepath))
        print('Created %s' % project.filepath)

if __name__ == '__main__':
    test()
