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
    def __init__(self, dictionary=None, label='', start=0, end=0, confidence=float('inf'), notes=''):
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
        self._is_deleted = False # Avoid multiple deletions

    def getKey(self,key):
        return self.element_dict[key]

    def setKey(self,key,value):
        self.element_dict[key] = value
        self.sigAnnotationElementChanged.emit(self)

    def getLabel(self):
        return self.element_dict['label']

    def setLabel(self, label):
        self.element_dict['label'] = label
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
        if not self._is_deleted:
            self._is_deleted = True
            # print('Emiting deletion signal from annotation:', self.getLabel(),self.getStart())
            # print('receivers:', QObject.receivers(self,self.sigAnnotationElementDeleted))
            self.sigAnnotationElementDeleted.emit(self)

    # def __del__(self):
    #      print('Annotation completely removed')

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

    def __init__(self, alist=None, fname=None, dic=None, history = [],history_step=-1):
        super().__init__()
        if dic is not None:
            self.annotations_list = [AnnotationElement(annotation) for annotation in dic['annotations_list']]
            self.labels = dic['labels']
            self.label_color_dict = dic['label_color_dict']
            if 'label_channel_range_dict' in dic.keys():  #Back compatibility with projects before label_channel_range
                self.label_channel_range_dict = dic['label_channel_range_dict']
            else:
                self.label_channel_range_dict = dict([(label,None) for label in self.labels])
        elif alist is not None and self.checklist(alist):
            self.annotations_list = alist
            self.labels = list(set([annotation.getLabel() for annotation in alist]))
            self.label_color_dict = {}
            n = max(len(self.labels),6)  # make space for at least 6 colors, or space all colors equally
            for i,label in enumerate(self.labels):
                self.label_color_dict[label] = tuple(np.array(colorsys.hls_to_rgb(i / n, .5, .9)) * 255)
                self.label_channel_range_dict[label] = None
        elif fname is not None:
            self.import_from_json(fname)
        else:
            self.annotations_list = []
            self.labels = []
            self.label_color_dict = {}  # dictionary to save label plotting colors
            self.label_channel_range_dict = {}
        self.focused_annotation = None
        self.history = history
        self.history_step = history_step
        self.history_is_paused = False
        if not self.history: # add oneself to history if it is empty
            self.clear_history()
        self.connect_annotations_to_history()


    def copy_from(self, annotation_page, clear_history=True):
        self.__dict__ = annotation_page.__dict__
        if not hasattr(annotation_page, 'label_channel_range_dict'):  # Back compatibility with projects before label_channel_range
            self.label_channel_range_dict = dict([(label, None) for label in self.labels])
        print(self.labels)
        self.sigLabelsChanged.emit('')
        self.connect_annotations_to_history()
        if clear_history:
            self.clear_history() # Reset history
            print('copy from - history reset')
            self.cache_to_history()

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
        annotation.sigAnnotationElementChanged.connect(self.cache_to_history)
        self.sigAnnotationAdded.emit(annotation)
        print('add annotation')
        self.cache_to_history()

    def delete_annotation(self, annotation,cache_history = True):
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
            if cache_history:
                print('delete annotation')
                self.cache_to_history()

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

    def delete_all_with_label(self, label,cache_history=True):
        for i, a in reversed(list(enumerate(self.annotations_list))):
            if a.getLabel() == label:
                self.delete_annotation(i,cache_history=False)
        if cache_history:
            print('delete all with label')
            self.cache_to_history()

    def delete_label(self, label):
        print('labels before delete',self.labels)
        if label in self.labels:
            self.delete_all_with_label(label,cache_history=False)
            del self.label_color_dict[label]
            del self.label_channel_range_dict[label]
            for i, l in reversed(list(enumerate(self.labels))):
                if l == label:
                    del self.labels[i]
        print('labels after', self.labels)
        self.cache_to_history()

    def change_label_name(self,old_label, new_label):
        self.history_is_paused = True
        for annotation in self.get_all_with_label(old_label):
            annotation.setLabel(new_label)
        for i,l in enumerate(self.labels):
            if l == old_label:
                self.labels[i] = new_label
        self.label_color_dict[new_label] = self.label_color_dict[old_label]
        self.label_channel_range_dict[new_label] = self.label_channel_range_dict[old_label]
        del self.label_color_dict[old_label]
        del self.label_channel_range_dict[old_label]
        self.sigLabelsChanged.emit(new_label)
        self.history_is_paused = False
        self.cache_to_history()
        print('change label name')

    def change_label_color(self,label,color):
        self.label_color_dict[label] = color
        self.sigLabelsChanged.emit(label)
        print('change label color')
        self.cache_to_history()

    def change_label_channel_range(self,label,channel_range):
        # Receives string and tries to interpret it as a list
        try:
            if not channel_range.startswith('['):
                channel_range = '[' + channel_range + ']'
            c = list(eval(channel_range))
        except Exception:
            c = None
        self.label_channel_range_dict[label] = c
        self.sigLabelsChanged.emit(label)
        print('change label range')
        self.cache_to_history()

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

            if label not in self.label_channel_range_dict.keys():
                self.label_channel_range_dict[label] = None

            self.sigLabelsChanged.emit(label)
            print('add label')
            self.cache_to_history()
        else:
            print('Annotations: Label already exists')

    def export_to_json(self, fname):
        # convert annotation objects into dictionaries
        full_dict = [json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list]
        with open(fname, 'w') as f:
            json.dump([full_dict,list(self.labels),self.label_color_dict,self.label_channel_range_dict], f, indent=4)

    def import_from_json(self, fname):
        with open(fname, 'r') as f:
            object_list = json.load(f)
        full_dict = object_list[0]
        # convert dictionaries into annotation objects
        self.annotations_list = [AnnotationElement(dictionary=a) for a in full_dict]
        self.labels = object_list[1]
        self.label_color_dict = object_list[2]
        self.label_channel_range_dict = object_list[3]
        self.connect_annotations_to_history()
        self.clear_history()
        print('import from json')

    def export_to_csv(self, fname, label): # Currently not in use
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
        # Copy more deeply some of the fields
        dict['annotations_list'] = [annotation.dict() for annotation in self.annotations_list]
        dict['labels'] = self.labels.copy()
        dict['label_color_dict'] = self.label_color_dict.copy()
        dict['label_channel_range_dict'] = self.label_channel_range_dict.copy()
        dict['focused_annotation'] = None
        dict['history'] = None
        dict['history_step'] = None
        return dict

    def restore_from_dict(self,dic):
        # to be used with history dictionaries so that history is not overwriten as would happen with shallower copies
        self.annotations_list = [AnnotationElement(annotation) for annotation in dic['annotations_list']]
        self.labels = dic['labels'].copy()
        self.label_color_dict = dic['label_color_dict'].copy()
        self.label_channel_range_dict = dic['label_channel_range_dict'].copy()
        self.sigLabelsChanged.emit('')
        self.connect_annotations_to_history()

    def pause_history_cache(self, pause = True):
        self.history_is_paused = pause

    def clear_history(self):
        self.history=[]
        self.cache_to_history()

    def cache_to_history(self,dummy_argument=None):
        if self.history_is_paused:
            # print('skiping history cache')
            return
        for k in range(1,-self.history_step):
            del self.history[-1] # delete history after current event
        self.history.append(self.dict())
        self.history_step=-1
        # print('Caching to history, history size:',len(self.history),dummy_argument)
        # for i,d in enumerate(self.history):
        #     print(i,d['labels'])
        if len(self.history) >= 10: # delete history buffer older than 10 events
            del self.history[0]

    def step_back_in_history(self):
        if len(self.history) > -self.history_step:
            self.history_step -= 1
            print('going back to step', self.history_step,'of history',len(self.history))
            for d in self.history:
                print(d['labels'])
            self.restore_from_dict(self.history[self.history_step])
        else:
            print('cannot go further back in history: step',self.history_step,'of:',-len(self.history))

    def step_forward_in_history(self):
        if self.history_step>=-1:
            print('Already at most recent point in history')
        else:
            self.history_step += 1
            # print('going forward to step', self.history_step,'of history',len(self.history))
            self.restore_from_dict(self.history[self.history_step])

    def connect_annotations_to_history(self):
        for annotation in self.annotations_list:
            annotation.sigAnnotationElementChanged.connect(self.cache_to_history)