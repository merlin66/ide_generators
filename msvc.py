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

import hashlib
import ntpath
import os
import sys

import xml.etree.cElementTree as ET
from xml.dom import minidom

# From SCons
external_makefile_guid = '{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}'

sln_headers = {
    8.0  : "Microsoft Visual Studio Solution File, Format Version 9.00\n# Visual Studio 2005\n",
    9.0  : "Microsoft Visual Studio Solution File, Format Version 10.00\n# Visual Studio 2008\n",
    10.0 : "Microsoft Visual Studio Solution File, Format Version 11.00\n# Visual Studio 2010\n",
}

configuration_types = {
    'Makefile'       : 0,
    'Application'    : 1,
    'DynamicLibrary' : 2,
    'StaticLibrary'  : 4,
    'Utility'        : 10,
}

configuration_tools = {
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
    m.update(ntpath.normpath(str(slnfile)) + str(name))
    solution = m.hexdigest().upper()
    # convert most of the signature to GUID form (discard the rest)
    solution = "{" + solution[:8] + "-" + solution[8:12] + "-" + solution[12:16] + "-" + solution[16:20] + "-" + solution[20:32] + "}"
    return solution

class Project():
    def __init__(self, filepath, archs, variants, files, project_info, name = None, src_root = None):
        self.filepath = filepath
        self.archs = archs
        self.variants = variants
        self.project_info = project_info
        self.configuration_type = project_info['project_type']
        self.files = files
        self.name = name
        self.src_root = src_root
        if name is None:
            self.name = os.path.splitext(os.path.split(filepath)[-1])[0]

        self.guid = _generateGUID(filepath, name)

    def get_tool_info(self, tool, variant, arch):
        possible_keys = [
            '%s|%s|%s' % (tool, variant, arch),
            '%s|%s' % (tool,variant),
            '%s|%s' % (tool,arch),
            tool,
            ]
        for key in possible_keys:
            try:
                return self.project_info[key]
            except KeyError:
                pass
        return dict()

def _add_file_nodes(parent_node, filemap, project_path, src_root):
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

def write_project(version, project, out):
    encoding = 'utf-8'
    pretty = True

    xml_project = ET.Element('VisualStudioProject',
        ProjectType            = 'Visual C++',
        Version                = '{0:.2f}'.format(version),
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
            tools = configuration_tools[project.configuration_type]
            for tool in tools:
                d = project.get_tool_info(tool, variant, arch)
                tool = ET.SubElement(configuration, 'Tool', Name = tool, **d)

    references = ET.SubElement(xml_project, 'References')
    files = ET.SubElement(xml_project, 'Files')
    if project.files:
        _add_file_nodes(parent_node = files, filemap = project.files, project_path = project.filepath, src_root = project.src_root)

    xml_globals = ET.SubElement(xml_project, 'Globals')

    # == write resulting xml ==
    if pretty:
        s = ET.tostring(xml_project)
        out.write(minidom.parseString(s).toprettyxml(encoding = encoding))
    else:
        doc = ET.ElementTree(xml_project)
        out.write('<?xml version="1.0" encoding="%s"?>\n' % encoding)
        doc.write(out, encoding = encoding)

def write_solution(version, projects, variants, archs, dependencies, out):
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
def _get_test_projects(variants, archs):
    project_files = [
        'test.vcproj',
        'testfolder/test2.vcproj',
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
        #'project_type' : 'Application',

        'VCNMakeTool' : dict(
            BuildCommandLine="scons.bat",
            CleanCommandLine="scons.bat -c",
            RebuildCommandLine="scons.bat -c && scons.bat",
            Output="foo.exe",
            ),
    }

    projects = [ Project(filepath = p,
                         variants = variants,
                         archs = archs,
                         files = files,
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
    version = 9.0
    sln_name = 'testsolution.sln'
    projects, dependencies = _get_test_projects(variants, archs)

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
    print 'Created %s' % sln_name

    for project in projects:
        out = open(os.path.join(testroot, project.filepath), 'w')
        write_project(version = version,
                      project = project,
                      out = out)
        out.close()
        print 'Created %s' % project.filepath

if __name__ == '__main__':
    test()
