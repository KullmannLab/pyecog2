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
import pyqtgraph.parametertree.parameterTypes as pTypes
from pyqtgraph.parametertree import Parameter, ParameterTree

## this group includes a menu allowing the user to add new parameters into its child list
class ScalableGroup(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add label"
        opts['addList'] = ['auto','red','green','blue'] #,'yellow','magenta','cyan']
        pTypes.GroupParameter.__init__(self, **opts)

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
        if val == 'auto':
            v = i_spaced_nfold(n,6)
            val = tuple(np.array(colorsys.hls_to_rgb(v, .5, .9)) * 255)
        self.addChild(
            dict(name="Label %d" % (len(self.childs) + 1), type='color', value=val, removable=True, renamable=True))

class AnnotationParameterTee(ParameterTree):
    def __init__(self,annotations):
        ParameterTree.__init__(self)
        self.annotationPage = annotations
        labels = self.annotationPage.labels
        print('Labels:', labels)
        Label_initial_dict = [{'name': label,
                               'type': 'color',
                               'value': self.annotationPage.label_color_dict[label],
                               'renamable': True,
                               'removable': True} for label in labels]
        self.params = [ScalableGroup(name="Annotation Labels", children=Label_initial_dict)]
        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        self.p.sigTreeStateChanged.connect(self.change)
        self.setParameters(self.p, showTop=False)
        self.headerItem().setHidden(True)
        self.annotationPage.sigLabelsChanged.connect(lambda s: self.re_init())


    def re_init(self):
        print('***************  Re_init Called ')
        self.p.sigTreeStateChanged.disconnect()
        Label_dict = [{'name': str(i+1) +': '+ label,
                               'type': 'color',
                               'value': self.annotationPage.label_color_dict[label],
                               'renamable': True,
                               'removable': True} for i, label in enumerate(self.annotationPage.labels)]
        self.p.clearChildren()
        self.params = [ScalableGroup(name="Annotation Labels", children=Label_dict)]
        self.p.addChildren(self.params)
        self.p.sigTreeStateChanged.connect(self.change)


    ## If anything changes in the tree, print a message
    def change(self, param, changes):
        print("tree changes:")
        for param, change, data in changes:
            path = self.p.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            print('  parameter: %s' % childName)
            print('  change:    %s' % change)
            print('  data:      %s' % str(data))
            print('  ----------')
            if change == 'value':
                label = path[-1].split(': ')[-1]
                color = (data.red(), data.green(), data.blue())
                self.annotationPage.change_label_color(label,color)
            if change == 'name':
                new_labels = [c.name().split(': ')[-1] for c in self.p.child('Annotation Labels').children()]
                print('new labels:',new_labels)
                for old_label in self.annotationPage.labels:
                    if old_label not in new_labels:
                        self.annotationPage.change_label_name(old_label, data.split(':')[-1])
            if change == 'childRemoved':
                label = data.name().split(': ')[-1]
                self.annotationPage.delete_label(label)
            if change == 'childAdded':
                label = data[0].name().split(': ')[-1]
                qcolor = data[0].value()
                color = (qcolor.red(), qcolor.green(), qcolor.blue())
                print('adding label', label, color)
                self.annotationPage.add_label(label, color)
