import json
from PyQt5 import QtCore
from PyQt5.QtCore import QObject
import numpy as np
import colorsys


class AnnotationElement(QObject):
    sigAnnotationElementChanged = QtCore.pyqtSignal(object) # emited when any attribute is changed
    sigAnnotationElementDeleted = QtCore.pyqtSignal(object) # emited when all references to annotation are deleted
    def __init__(self, dictionary=None, label='', start=0, end=0, confidence=1, notes=''):
        super().__init__()
        if dictionary is not None:
            self.element_dict = dictionary
        else:
            self.element_dict = {'label': label,
                                 'start': start,
                                 'end': end,
                                 'notes': notes,
                                 'confidence': confidence}  # To be used by classifier predictions

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
        return [self.element_dict['start'], self.element_dict['start']]

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

    def __del__(self):
        self.sigAnnotationElementDeleted.emit(self)

    def __repr__(self):
        return repr(self.element_dict)

    def __str__(self):
        return str(self.element_dict)

class AnnotationPage:
    def __init__(self, list=None, fname=None):
        if list is not None and self.checklist(list):
            self.annotations_list = list
            self.labels = set([annotation.getLabel() for annotation in list])
            self.label_color_dict = {}
            n = max(len(self.labels),6)  # make space for at least 6 colors, or space all colors equally
            for i,label in enumerate(self.labels):
                self.label_color_dict[label] = tuple(np.array(colorsys.hls_to_rgb(i / n, .5, .9)) * 255)

        elif fname is not None:
            self.import_from_json(fname)
        else:
            self.annotations_list = []
            self.labels = set()
            self.label_color_dict = {}  # dictionary to save label plotting colors

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
        self.labels.add(annotation.getLabel())

    def delete_annotation(self, index):
        try:
            self.annotations_list[index].delete() # send signal we are deleting annotation
            del self.annotations_list[index]
        except IndexError:
            print('Annotation index is out of range')

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

    def add_label(self, label):
        if label not in self.labels:
            self.labels.add(label) # for future if labels can have global propreties... probably will never be used
        else:
            print('Annotations: Label already exists')

    def export_to_json(self, fname):
        # convert annotation objects into dictionaries
        full_dict = [json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list]
        with open(fname, 'w') as f:
            json.dump([full_dict,list(self.labels),self.label_color_dict], f)

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



# To be deleted after refactoring

class Annotations:
    def __init__(self, dictionary=None, fname=None):
        if dictionary is not None and self.check_dict(dictionary):
            self.annotations_dict = dictionary
            self.labels = self.annotations_dict.keys()
        elif fname is not None:
            self.import_from_json(fname)
        else:
            self.annotations_dict = {}
            self.labels = self.annotations_dict.keys()

    @staticmethod
    def check_dict(dictionary):  # try to check if dictionary structure is valid
        if type(dictionary) is not dict:
            return False
        # Now check that all labels have lists of lists of length 2, with numbers inside : TO DO
        if not all([type(dictionary[label]) == list for label in dictionary]):
            print('Annotations: invalid type for annotations dictionary')
            return False
        if not all([all([len(i) == 2 for i in dictionary[label]]) for label in dictionary]):
            print('Annotations: invalid length(s) for [start, end] of annotations')
            return False
        if not all(
                [all([all([type(j) in [int, float] for j in i]) for i in dictionary[label]]) for label in dictionary]):
            print('Annotations: invalid data type for start and end of annotations')
            return False
        return True

    def add_annotation(self, label, tstart, tend):
        if label in self.labels:
            self.annotations_dict[label].append([tstart, tend])
        else:
            self.add_label(label)
            self.annotations_dict[label] = [[tstart, tend]]

    def delete_annotation(self, label, index):
        try:
            del self.annotations_dict[label][index]
        except IndexError:
            print('Annotation index is out of range')

    def delete_label(self, label):
        del self.annotations_dict[label]
        self.labels = self.annotations_dict.keys()

    def add_label(self, label):
        if label not in self.labels:
            self.annotations_dict[label] = []
            self.labels = self.annotations_dict.keys()
        else:
            print('Annotations: Label already exists')

    def set_annotation_times(self, label, index, tstart, tend):
        self.annotations_dict[label][index] = [tstart, tend]
        print(self.annotations_dict)  # For debug

    def get_all_annotation_times(self, label):
        return [i for i in self.annotations_dict[label]]

    def get_all_start_times(self, label):
        return [i[0] for i in self.annotations_dict[label]]

    def get_all_end_times(self, label):
        return [i[1] for i in self.annotations_dict[label]]

    def import_from_json(self, fname):
        with open(fname, 'r') as f:
            self.annotations_dict = json.load(f)
        if not self.check_dict(self.annotations_dict):
            self.annotations_dict = {}
            print('Annotations: invalid dictionary in Json file')
        self.labels = self.annotations_dict.keys()

    def export_to_json(self, fname):
        with open(fname, 'w') as f:
            json.dump(self.annotations_dict, f)

    def export_to_csv(self, fname, label):
        with open(fname, 'w') as f:
            f.write(label + ',' + 'start,stop\n')
            for i, j in enumerate(self.annotations_dict[label]):
                f.write(str(i) + ',' + str(j[0]) + ',' + str(j[1]) + '\n')

    def __repr__(self):
        return repr(self.annotations_dict)

    def __str__(self):
        return str(self.annotations_dict)
