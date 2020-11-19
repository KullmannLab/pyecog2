import json
from PyQt5 import QtCore
from PyQt5.QtCore import QObject
import numpy as np
import colorsys
from collections import OrderedDict

# Function to generate nicely spaced colors (i.e. points around a ring)
def i_spaced_nfold(i,n):
    n =max(n,1)
    floorlog = np.floor(np.log2(max(2*(i-1)/n,1)))
    d = n*2**floorlog
    if d == n:
        h = i-1
    else:
        h = (2*i - d - 1)
    v = h/d
    return v

class AnnotationElement(QObject):
    sigAnnotationElementChanged = QtCore.pyqtSignal(object) # emited when any attribute is changed
    sigAnnotationElementDeleted = QtCore.pyqtSignal(object) # emited when all references to annotation are deleted
    def __init__(self, dictionary=None, label='', start=0, end=0, confidence=1, notes=''):
        super().__init__()
        if dictionary is not None:
            header = ['label', 'start', 'end', 'confidence', 'notes']
            self.element_dict = OrderedDict(sorted(dictionary.items(), key=lambda l: header.index(l[0])))
        else:
            # self.element_dict = {'label': label,
            #                      'start': start,
            #                      'end': end,
            #                      'confidence': confidence,
            #                      'notes': notes}  # To be used by classifier predictions
            self.element_dict = OrderedDict([('label', label),
                                             ('start', float(start)),
                                             ('end', float(end)),
                                             ('confidence', float(confidence)),
                                             ('notes', notes)])  # To be used by classifier predictions

    def getKey(self,key):
        return self.element_dict[key]

    def setKey(self,key,value):
        self.element_dict[key] = value
        self.sigAnnotationElementChanged.emit(self)

    def getLabel(self):
        return self.element_dict['label']

    def setLabel(self, start):
        self.element_dict['label'] = start
        self.sigAnnotationElementChanged.emit(self)

    def getStart(self):
        return self.element_dict['start']

    def setStart(self, start):
        self.element_dict['start'] = start
        self.sigAnnotationElementChanged.emit(self)

    def getEnd(self):
        return self.element_dict['end']

    def setEnd(self, end):
        self.element_dict['end'] = end
        self.sigAnnotationElementChanged.emit(self)

    def getPos(self):
        return [self.element_dict['start'], self.element_dict['end']]

    def setPos(self, pos):
        self.element_dict['start'] = min(pos)
        self.element_dict['end'] = max(pos)
        self.sigAnnotationElementChanged.emit(self)

    def getNotes(self):
        return self.element_dict['notes']

    def setNotes(self, notes):
        self.element_dict['notes'] = notes
        self.sigAnnotationElementChanged.emit(self)

    def getConfidence(self):
        return self.element_dict['confidence']

    def setConfidence(self, confidence):
        self.element_dict['confidence'] = confidence
        self.sigAnnotationElementChanged.emit(self)

    def delete(self):
        self.sigAnnotationElementDeleted.emit(self)

    # def __del__(self):
    #      self.sigAnnotationElementDeleted.emit(self)

    def __repr__(self):
        return repr(dict(self.element_dict))

    def __str__(self):
        return str(dict(self.element_dict))

    def dict(self):
        return self.element_dict.copy()

class AnnotationPage(QObject):
    sigFocusOnAnnotation = QtCore.pyqtSignal(object)
    sigAnnotationAdded   = QtCore.pyqtSignal(object)
    sigLabelsChanged     = QtCore.pyqtSignal(object)

    def __init__(self, alist=None, fname=None, dict=None):
        super().__init__()
        if dict is not None:
            self.annotations_list = [AnnotationElement(annotation) for annotation in dict['annotations_list']]
            self.labels = dict['labels']
            self.label_color_dict = dict['label_color_dict']
        elif alist is not None and self.checklist(alist):
            self.annotations_list = alist
            self.labels = list(set([annotation.getLabel() for annotation in alist]))
            self.label_color_dict = {}
            n = max(len(self.labels),6)  # make space for at least 6 colors, or space all colors equally
            for i,label in enumerate(self.labels):
                self.label_color_dict[label] = tuple(np.array(colorsys.hls_to_rgb(i / n, .5, .9)) * 255)

        elif fname is not None:
            self.import_from_json(fname)
        else:
            self.annotations_list = []
            self.labels = []
            self.label_color_dict = {}  # dictionary to save label plotting colors
        self.focused_annotation = None

    def copy_from(self, annotation_page):
        self.__dict__ = annotation_page.__dict__
        self.sigLabelsChanged.emit('')

    def copy_to(self, annotation_page):
        annotation_page.__dict__ = self.__dict__

    def focusOnAnnotation(self, annotation):
        if annotation != self.focused_annotation:
            self.focused_annotation = annotation
            print('focused on', annotation)
            self.sigFocusOnAnnotation.emit(annotation)

    @staticmethod
    def checklist(alist):  # try to check if dictionary structure is valid
        if type(alist) is not list:
            print('Annotations: invalid type for annotations list')
            return False
        # Now check that all elements are of type AnnotationElement
        if not all([isinstance(annotation, AnnotationElement) for annotation in alist]):
            print('Annotations: invalid type for annotations list elements')
            return False
        return True

    def add_annotation(self, annotation):
        self.annotations_list.append(annotation)
        self.add_label(annotation.getLabel())
        self.sigAnnotationAdded.emit(annotation)

    def delete_annotation(self, annotation):
        if type(annotation) is not int:
            index = self.get_annotation_index(annotation)
        else:
            index = annotation # allow for annotation to be the index
            annotation = self.annotations_list[index]
        if index is None:
            return
        try:
            del self.annotations_list[index]
            annotation.delete() # send signal we are deleting annotation
        except IndexError:
            print('Annotation index is out of range')

    def get_annotation_index(self, annotation):
        for i in range(len(self.annotations_list)):
            if self.annotations_list[i] == annotation:
                return i
        return None

    def get_all_with_label(self, label):
        result = []
        for i, a in enumerate(self.annotations_list):
            if a.getLabel() == label:
                result.append(a)
        return result

    def delete_all_with_label(self, label):
        for i, a in reversed(list(enumerate(self.annotations_list))):
            if a.getLabel() == label:
                self.delete_annotation(i)

    def delete_label(self, label):
        print('labels before delete',self.labels)
        if label in self.labels:
            self.delete_all_with_label(label)
            del self.label_color_dict[label]
            for i, l in reversed(list(enumerate(self.labels))):
                if l == label:
                    del self.labels[i]
        print('labels after', self.labels)

    def change_label_name(self,old_label, new_label):
        for annotation in self.get_all_with_label(old_label):
            annotation.setLabel(new_label)
        for i,l in enumerate(self.labels):
            if l == old_label:
                self.labels[i] = new_label
        self.label_color_dict[new_label] = self.label_color_dict[old_label]
        del self.label_color_dict[old_label]
        self.sigLabelsChanged.emit(new_label)

    def change_label_color(self,label,color):
        self.label_color_dict[label] = color
        self.sigLabelsChanged.emit(label)

    def add_label(self, label, color = None):
        print(label,color,self.labels)
        if label not in self.labels:
            self.labels.append(label) # for future if labels can have global propreties... probably will never be used
            if label not in self.label_color_dict.keys():
                if color is not None:
                    self.label_color_dict[label] = color
                else:
                    n = len(self.labels)
                    h = i_spaced_nfold(n,6)
                    self.label_color_dict[label] = tuple(np.array(colorsys.hls_to_rgb(h, .5, .9)) * 255)
            self.sigLabelsChanged.emit(label)
        else:
            print('Annotations: Label already exists')

    def export_to_json(self, fname):
        # convert annotation objects into dictionaries
        full_dict = [json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list]
        with open(fname, 'w') as f:
            json.dump([full_dict,list(self.labels),self.label_color_dict], f, indent=4)

    def import_from_json(self, fname):
        with open(fname, 'r') as f:
            object_list = json.load(f)
        full_dict = object_list[0]
        # convert dictionaries into annotation objects
        self.annotations_list = [AnnotationElement(dictionary=a) for a in full_dict]
        self.labels = set(object_list[1])
        self.label_color_dict = object_list[2]

    def export_to_csv(self, fname, label):
        with open(fname, 'w') as f:
            f.write(label + ',' + 'start,stop\n')
            for i, a in enumerate(self.annotations_list):
                if a.getLabel() == label:
                    f.write(str(i) + ',' + str(a.getStart()) + ',' + str(a.getEnd()) + '\n')

    def __repr__(self):
        return repr([json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list])

    def __str__(self):
        return str([json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list])

    def dict(self):
        dict = self.__dict__.copy()
        dict['annotations_list'] = [annotation.dict() for annotation in self.annotations_list]
        dict['focused_annotation'] = None
        return dict