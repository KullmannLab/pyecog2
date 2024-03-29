import json
from PySide2 import QtCore
from PySide2.QtCore import QObject
import numpy as np
import colorsys
from collections import OrderedDict
from timeit import default_timer as timer
import logging
logger = logging.getLogger(__name__)

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
    sigAnnotationElementChanged = QtCore.Signal(object) # emited when any attribute is changed
    sigAnnotationElementDeleted = QtCore.Signal(object) # emited when all references to annotation are deleted
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
            logger.info(f'Emiting deletion signal from annotation: {self.getLabel(), self.getStart()}')
            # print('receivers:', QObject.receivers(self.sigAnnotationElementDeleted))
            self.sigAnnotationElementDeleted.emit(self)

    # def __del__(self):
    #      print('Annotation completely removed')

    def __repr__(self):
        return repr(dict(self.element_dict)).replace('"confidence": inf','"confidence": float("inf")')

    def __str__(self):
        return str(dict(self.element_dict)).replace('"confidence": inf','"confidence": float("inf")')

    def dict(self):
        return self.element_dict.copy()

class AnnotationPage(QObject):
    sigFocusOnAnnotation = QtCore.Signal(object)
    sigAnnotationAdded   = QtCore.Signal(object)
    sigLabelsChanged     = QtCore.Signal(object)
    sigPauseTable        = QtCore.Signal(bool)
    def __init__(self, alist=None, fname=None, dic=None, history = [],history_step=-1):
        super().__init__()
        if dic is not None:
            self.initialize_from_dict(dic,include_history=False)
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


    def initialize_from_dict(self,dic,include_history=True):
        if dic['annotations_list'] and type(dic['annotations_list'][0])==dict:
            self.annotations_list = [AnnotationElement(annotation) for annotation in dic['annotations_list']]
        else:
            self.annotations_list = dic['annotations_list']
        self.labels = dic['labels']
        self.label_color_dict = dic['label_color_dict']
        if 'label_channel_range_dict' in dic.keys():  # Back compatibility with projects before label_channel_range
            self.label_channel_range_dict = dic['label_channel_range_dict']
        else:
            self.label_channel_range_dict = dict([(label, None) for label in self.labels])

        if include_history:
            self.focused_annotation = dic['focused_annotation']
            self.history = dic['history']
            self.history_step = dic['history_step']
            self.history_is_paused = dic['history_is_paused']
            if not self.history:  # add oneself to history if it is empty
                self.clear_history()

    def copy_from(self, annotation_page, clear_history=True,connect_history=True,quiet = False):
        start_t=timer()
        # print('AnnotationPage copy_from start')
        # self.__dict__ = annotation_page.__dict__  # does not work with PySide
        self.initialize_from_dict(annotation_page.__dict__)
        if not quiet:
            self.sigLabelsChanged.emit('')
        if connect_history:
            self.connect_annotations_to_history()
        if clear_history:
            self.clear_history() # Reset history
            # print('copy from - history reset')

        # print('AnnotationPage copy_from finished in', timer()-start_t,'seconds')

    # def copy_to(self, annotation_page):
    #     annotation_page.__dict__ = self.__dict__

    def focusOnAnnotation(self, annotation):
        if annotation != self.focused_annotation:
            self.focused_annotation = annotation
            logger.info(f'focused on {annotation}')
            self.sigFocusOnAnnotation.emit(annotation)

    @staticmethod
    def checklist(alist):  # try to check if dictionary structure is valid
        if type(alist) is not list:
            logger.info('Annotations: invalid type for annotations list')
            return False
        # Now check that all elements are of type AnnotationElement
        if not all([isinstance(annotation, AnnotationElement) for annotation in alist]):
            logger.info('Annotations: invalid type for annotations list elements')
            return False
        return True

    def add_annotation(self, annotation):
        self.annotations_list.append(annotation)
        self.add_label(annotation.getLabel())
        annotation.sigAnnotationElementChanged.connect(self.cache_to_history)
        self.sigAnnotationAdded.emit(annotation)
        logger.info('add annotation')
        self.cache_to_history()

    def delete_annotation(self, annotation,cache_history = True):
        if type(annotation) is int:
            index = annotation # allow for annotation to be the index
            annotation = self.annotations_list[index]
        try:
            self.annotations_list.remove(annotation)
            annotation.delete() # send signal we are deleting annotation
            if cache_history:
                logger.info('delete annotation')
                self.cache_to_history()
        except IndexError:
            logger.info('Annotation index is out of range')
        except ValueError:
            logger.info('Annotation is not found in annotations_list')

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
        self.sigPauseTable.emit(True)
        for i, a in reversed(list(enumerate(self.annotations_list))):
            if a.getLabel() == label:
                self.delete_annotation(i,cache_history=False)
        if cache_history:
            logger.info('delete all with label')
            self.cache_to_history()

    def delete_label(self, label):
        logger.info(f'labels before delete {self.labels}')
        if label in self.labels:
            self.delete_all_with_label(label,cache_history=False)
            del self.label_color_dict[label]
            del self.label_channel_range_dict[label]
            for i, l in reversed(list(enumerate(self.labels))):
                if l == label:
                    del self.labels[i]
        logger.info(f'labels after {self.labels}')
        self.cache_to_history()
        self.sigPauseTable.emit(False)
        self.sigLabelsChanged.emit(None)

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
        logger.info('change label name')

    def change_label_color(self,label,color):
        self.label_color_dict[label] = color
        self.sigLabelsChanged.emit(label)
        logger.info('change label color')
        self.cache_to_history()

    def change_label_channel_range(self,label,channel_range):
        # Receives string and tries to interpret it as a list
        try:
            # if not channel_range.startswith('['):
            #     channel_range = '[' + channel_range + ']'
            c = eval(channel_range)
            if not hasattr(c,'__iter__'):
                c = [c]
            c = list(c)
            min(c) # check that we can compute min of c
        except Exception:
            c = None
        self.label_channel_range_dict[label] = c
        self.sigLabelsChanged.emit(label)
        logger.info('change label range')
        self.cache_to_history()

    def add_label(self, label, color = None):
        logger.info(f'Adding label: {label, color, self.labels}')
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
            logger.info('add label: sigLabelsChanged emitted')
            self.cache_to_history()
        else:
            logger.info('Annotations: Label already exists')

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
        logger.info('import from json')

    def export_to_csv(self, fname, label): # Currently not in use
        with open(fname, 'w') as f:
            f.write(label + ',' + 'start,stop,confidence,notes\n')
            for i, a in enumerate(self.annotations_list):
                if a.getLabel() == label:
                    f.write(str(i) + ',' + str(a.getStart()) + ',' + str(a.getEnd()) + ',' + str(a.getConfidence()) +
                            ',' + str(a.getNotes()) + '\n')

    def __repr__(self):
        return repr([json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list])

    def __str__(self):
        return str([json.loads(repr(a).replace('\'','\"')) for a in self.annotations_list])

    def dict(self):
        # dict = self.__dict__.copy()
        dic = {}
        # Copy more deeply some of the fields
        dic['annotations_list'] = [annotation.dict() for annotation in self.annotations_list]
        dic['labels'] = self.labels.copy()
        dic['label_color_dict'] = self.label_color_dict.copy()
        dic['label_channel_range_dict'] = self.label_channel_range_dict.copy()
        dic['focused_annotation'] = self.get_annotation_index(self.focused_annotation)
        dic['history'] = None
        dic['history_step'] = None
        dic['history_is_paused'] = False
        return dic

    def restore_from_dict(self,dic):
        # to be used with history dictionaries so that history is not overwriten as would happen with shallower copies
        self.annotations_list = [AnnotationElement(annotation) for annotation in dic['annotations_list']]
        self.labels = dic['labels'].copy()
        self.label_color_dict = dic['label_color_dict'].copy()
        self.label_channel_range_dict = dic['label_channel_range_dict'].copy()
        if dic['focused_annotation'] is not None:
            self.focusOnAnnotation(self.annotations_list[dic['focused_annotation']])
        self.sigLabelsChanged.emit('')
        self.connect_annotations_to_history()

    def pause_history_cache(self, pause = True):
        self.history_is_paused = pause

    def clear_history(self):
        self.history.clear()
        self.history_step = -1
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
            logger.info(f'going back to step {self.history_step} of history {len(self.history)}')
            for d in self.history:
                logger.info(f"{d['labels']}")
            self.restore_from_dict(self.history[self.history_step])
        else:
            logger.warning(f'Cannot go further back in history: step {self.history_step} of: {-len(self.history)}')

    def step_forward_in_history(self):
        if self.history_step>=-1:
            logger.info('Already at most recent point in history')
        else:
            self.history_step += 1
            # print('going forward to step', self.history_step,'of history',len(self.history))
            self.restore_from_dict(self.history[self.history_step])

    def connect_annotations_to_history(self):
        for annotation in self.annotations_list:
            annotation.sigAnnotationElementChanged.connect(self.cache_to_history)