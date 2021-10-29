# -*- coding: utf-8 -*-
"""
This example demonstrates the use of pyqtgraph's parametertree system. This provides
a simple way to generate user interfaces that control sets of parameters. The example
demonstrates a variety of different parameter types (int, float, list, etc.)
as well as some customized parameter types

"""
import numpy as np
import colorsys
from pyecog2.annotations_module import i_spaced_nfold
from pyqtgraph.parametertree import Parameter
from PySide2 import QtGui
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree, PyecogGroupParameter, PyecogGroupParameterItem
from timeit import default_timer as timer
from time import sleep

## this group includes a menu allowing the user to add new parameters into its child list
# class ScalableGroup(pTypes.GroupParameter):
class ScalableGroup(PyecogGroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add label"
        opts['addList'] = ['auto','red','green','blue'] #,'yellow','magenta','cyan']
        # pTypes.GroupParameter.__init__(self, **opts)
        PyecogGroupParameter.__init__(self, **opts)

    def addNew(self, typ):
        val = { 'auto':     'auto',
                'red':      (255,0,0),
                'green':    (0,255,0),
                'blue':     (0,0,255),
                # 'yellow':   (255,255,0),
                # 'magenta':  (255,0,255),
                # 'cyan':     (0,255,255),
                }[typ]

        n = (len(self.childs) + 1)
        while n<255:
            try:
                if val == 'auto':
                    v = i_spaced_nfold(n,6)
                    val = tuple(np.array(colorsys.hls_to_rgb(v, .5, .9)) * 255)
                self.addChild(
                    {'name': "Label %d" % n,
                     'type': 'group',
                     'children': [
                         {'name':'shortcut key','type':'int','value': n},
                         {'name': 'color', 'type': 'color', 'value':val},
                         {'name': 'Channel range', 'type': 'str','value': str(None)}],
                     'renamable': True,
                     'removable': True})
                break
            except Exception:
                print("Label %d" % n,'already exists')
                n +=1


class AnnotationParameterTee(PyecogParameterTree):
    def __init__(self,annotations):
        PyecogParameterTree.__init__(self)
        self.annotationPage = annotations
        labels = self.annotationPage.labels
        self.shortcut_keys = dict([(l, i+1) for i,l in enumerate(labels)])
        print('Labels:', labels)
        Label_initial_dict = [{'name': label,
                               'type': 'group',
                               'children':[
                                   {'name':'shortcut key','type':'int','value': self.shortcut_keys[label],'limits': (1, 10)},
                                   {'name':'color','type':'color', 'value':self.annotationPage.label_color_dict[label]},
                                   {'name': 'Channel range', 'type': 'str',
                                    'value': str(self.annotationPage.label_channel_range_dict[label])}
                                          ],
                               'renamable': True,
                               'removable': True} for i, label in enumerate(labels)]

        self.params = [ScalableGroup(name="Annotation Labels", children=Label_initial_dict)]
        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        self.p.sigTreeStateChanged.connect(self.change)
        self.setParameters(self.p, showTop=False)
        self.headerItem().setHidden(True)
        # self.update_color_from_group_parameters()
        # self.last_label_change = None
        self.annotationPage.sigLabelsChanged.connect(self.re_init)

    def re_init(self,label=None): # dummy variable to connect to sigLabelsChanged
        # if self.last_label_change == label:
        #     print('re_init already ran for', label)
        #     return # skip re_init because it already ran
        # self.last_label_change = label
        start_t = timer()
        print('AnnotationParameterTree Re_init Called ', label)
        self.p.sigTreeStateChanged.disconnect()
        labels = self.annotationPage.labels
        if set(labels) != set(self.shortcut_keys.keys()):  # restart shortcut keys in case labels change in annotationPage
            self.shortcut_keys = dict([(l, i + 1) for i, l in enumerate(labels)])
        # print('AnnotationParameterTree Re_init shortcuts redefined (', timer()-start_t, 'seconds )')

        Label_dict = [{'name': label,
                               'type': 'group',
                               'children':[
                                   {'name':'shortcut key','type':'int','value': self.shortcut_keys[label],'limits': (1, 10)},
                                   {'name':'color','type':'color', 'value':self.annotationPage.label_color_dict[label]},
                                   {'name': 'Channel range', 'type': 'str',
                                    'value': str(self.annotationPage.label_channel_range_dict[label])}
                                          ],
                               'renamable': True,
                               'removable': True} for i, label in enumerate(labels)]
        # print('AnnotationParameterTree Re_init label_dict generated (', timer()-start_t, 'seconds )')
        self.p.clearChildren()
        # print('AnnotationParameterTree Re_init children cleard (', timer()-start_t, 'seconds )')
        self.params = [ScalableGroup(name="Annotation Labels", children=Label_dict)]
        # print('AnnotationParameterTree Re_init params created (', timer()-start_t, 'seconds )')

        # self.p.addChildren(self.params) # this line  was taking increasingly long at each run, so reinstantiating self.p altogether
        self.p = Parameter.create(name='params', type='group', children=self.params)

        # print('AnnotationParameterTree Re_init children added (', timer()-start_t, 'seconds )')
        # self.update_color_from_group_parameters()
        self.setParameters(self.p, showTop=False)
        # print('AnnotationParameterTree Parameters set(', timer()-start_t, 'seconds )')
        self.headerItem().setHidden(True)
        self.p.sigTreeStateChanged.connect(self.change)
        # print('AnnotationParameterTree Re_init finished (', timer()-start_t, 'seconds )')


    ## If anything changes in the tree, print a message
    def change(self, param, changes):
        # print("tree changes:")
        for param, change, data in changes:
            path = self.p.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            # print('  parameter: %s' % childName)
            # print('  change:    %s' % change)
            # print('  data:      %s' % str(data))
            # print('  ----------')
            if change == 'value':  # check for changes in colors, rangesand shrotcurs
                label = path[-2]
                if path[-1] == 'color':
                    color = (data.red(), data.green(), data.blue())
                    self.annotationPage.change_label_color(label,color)
                elif path[-1] == 'Channel range':
                    # print('setting new channel range',data,'for label',label)
                    self.annotationPage.change_label_channel_range(label,str(data))
                elif path[-1] == 'shortcut key':
                    self.shortcut_keys[label] = data
            if change == 'name':  # check for changes in labels
                new_labels = [c.name() for c in self.p.child('Annotation Labels').children()]
                # print('new labels:', new_labels)
                for old_label in self.annotationPage.labels:
                    if old_label not in new_labels:
                        self.shortcut_keys[data] = self.shortcut_keys[old_label]
                        del self.shortcut_keys[old_label]
                        self.annotationPage.change_label_name(old_label, data)
            if change == 'childRemoved':
                label = data.name()
                del self.shortcut_keys[label]
                # print('Shortcut Keys:',self.shortcut_keys)
                self.annotationPage.delete_label(label)
            if change == 'childAdded':
                label = data[0].name()
                qcolor = data[0].children()[1].value()
                color = (qcolor.red(), qcolor.green(), qcolor.blue())
                # print('adding label', label, color)
                self.shortcut_keys[label] = len(self.shortcut_keys) +1
                self.annotationPage.add_label(label, color)

    def get_label_from_shortcut(self,shortcutkey):
        # p_list = self.params[0].children()
        # # label_list = [(p.children()[0].value(),p.name()) for p in p_list]
        # # print('shortcut,label:', label_list)
        # label = None
        # for p in p_list:
        #     if p.children()[0].value() == shortcutkey:
        #         label = p.name()
        # return label
        label = None
        # print('Shortcut Keys:', self.shortcut_keys)
        # print('looking for key', shortcutkey)
        for label in self.shortcut_keys.keys():
            if self.shortcut_keys[label] == shortcutkey:
                return label
