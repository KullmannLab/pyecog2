import json

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
        if not all([all([all([type(j) in [int, float] for j in i]) for i in dictionary[label]]) for label in dictionary]):
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
        print(self.annotations_dict) # For debug

    def get_all_annotation_times(self,label):
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
            for i,j in enumerate(self.annotations_dict[label]):
                f.write(str(i) + ',' + str(j[0]) + ',' + str(j[1]) + '\n')

    def __repr__(self):
        return repr(self.annotations_dict)

    def __str__(self):
        return str(self.annotations_dict)