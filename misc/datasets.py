from __future__ import division
from __future__ import print_function

import numpy as np
import pickle
import random


class Dataset(object):
    def __init__(self, images, imsize, embeddings=None,
                 filenames=None, workdir=None,
                 labels=None, aug_flag=True,
                 class_id=None, class_range=None):
        self._images = images
        self._embeddings = embeddings
        self._filenames = filenames
        self.workdir = workdir
        self._labels = labels
        self._epochs_completed = -1
        self._num_examples = len(images)
        self._saveIDs = self.saveIDs()

        # shuffle on first run
        self._index_in_epoch = self._num_examples
        self._aug_flag = aug_flag
        self._class_id = np.array(class_id)
        self._class_range = class_range
        self._imsize = imsize
        self._perm = None

    @property
    def images(self):
        return self._images

    @property
    def embeddings(self):
        return self._embeddings

    @property
    def filenames(self):
        return self._filenames

    @property
    def num_examples(self):
        return self._num_examples

    @property
    def epochs_completed(self):
        return self._epochs_completed

    @property
    def imsize(self):
        return self._imsize

    def saveIDs(self):
        self._saveIDs = np.arange(self._num_examples)
        np.random.shuffle(self._saveIDs)
        return self._saveIDs

    def readCaptions(self, filenames, class_id):
        name = filenames
        if name.find('jpg/') != -1:  # flowers dataset
            class_name = 'class_%05d/' % class_id
            name = name.replace('jpg/', class_name)
        cap_path = '%s/text_c10/%s.txt' % \
                   (self.workdir, name)
        with open(cap_path, "r") as f:
            captions = f.read().split('\n')
        captions = [cap for cap in captions if len(cap) > 0]
        return captions

    def transform(self, images, sketches=None, jitter=True):
        if self._aug_flag:
            batch_size = images.shape[0]
            transformed_images = np.zeros([batch_size, self._imsize, self._imsize, 3])
            transformed_sketches = None
            if sketches is not None:
                transformed_sketches = np.zeros([batch_size, self._imsize, self._imsize, 1])
            ori_size = images.shape[1]
            for i in range(images.shape[0]):
                h1 = np.floor((ori_size - self._imsize) * np.random.random())
                w1 = np.floor((ori_size - self._imsize) * np.random.random())
                # h1 = np.floor((ori_size - self._imsize) * 0.5)
                # w1 = np.floor((ori_size - self._imsize) * 0.5)
                cropped_image = images[i][w1: w1 + self._imsize, h1: h1 + self._imsize, :]

                # if jitter:
                #     for j in range(3):
                #         if random.random() > 0.5:
                #             cropped_image[:, :, j] *= (0.75 + 0.5 * random.random())
                #     cropped_image = np.minimum(255.0, cropped_image)

                if sketches is not None:
                    cropped_sketches = sketches[i][w1: w1 + self._imsize, h1: h1 + self._imsize, :]
                if random.random() > 0.5:
                    transformed_images[i] = np.fliplr(cropped_image)
                    if sketches is not None:
                        transformed_sketches[i] = np.fliplr(cropped_sketches)#.flatten()
                else:
                    transformed_images[i] = cropped_image
                    if sketches is not None:
                        transformed_sketches[i] = cropped_sketches#.flatten()

            return transformed_images, transformed_sketches

        return images, sketches

    def sample_embeddings(self, embeddings, filenames, class_id, sample_num):
        if embeddings.shape[1] == 1:  # if only 1 embedding per image
            return np.squeeze(embeddings, axis=1), ['no caption'] * embeddings.shape[0]
        else:
            batch_size, embedding_num, _ = embeddings.shape
            # Take every sample_num captions to compute the mean vector
            sampled_embeddings = []
            sampled_captions = []
            for i in range(batch_size):
                randix = np.random.choice(embedding_num,
                                          sample_num, replace=False)
                if sample_num == 1:
                    randix = int(randix)
                    captions = self.readCaptions(filenames[i],
                                                 class_id[i])
                    sampled_captions.append(captions[randix])
                    sampled_embeddings.append(embeddings[i, randix, :])
                else:
                    e_sample = embeddings[i, randix, :]
                    e_mean = np.mean(e_sample, axis=0)
                    sampled_embeddings.append(e_mean)
            sampled_embeddings_array = np.array(sampled_embeddings)
            return np.squeeze(sampled_embeddings_array, axis=1), sampled_captions
            # return sampled_embeddings_array, sampled_captions

    def next_batch(self, batch_size, window):
        """Return the next `batch_size` examples from this data set."""
        start = self._index_in_epoch
        self._index_in_epoch += batch_size

        if self._index_in_epoch > self._num_examples:
            # Finished epoch
            self._epochs_completed += 1
            # Shuffle the data
            self._perm = np.arange(self._num_examples)
            np.random.shuffle(self._perm)

            # Start next epoch
            start = 0
            self._index_in_epoch = batch_size
            assert batch_size <= self._num_examples
        end = self._index_in_epoch

        current_ids = self._perm[start:end]
        fake_ids = np.random.randint(self._num_examples, size=batch_size)
        collision_flag = (self._class_id[current_ids] == self._class_id[fake_ids])
        fake_ids[collision_flag] = \
            (fake_ids[collision_flag] +
             np.random.randint(100, 200)) % self._num_examples
        # fake_ids = current_ids[::-1]

        sampled_images = self._images[current_ids]
        sampled_wrong_images = self._images[fake_ids, :, :, :]
        sampled_images = sampled_images.astype(np.float32)
        sampled_wrong_images = sampled_wrong_images.astype(np.float32)

        # sampled_embeddings, sampled_captions = None, None
        # if self._embeddings is not None:
        #     filenames = [self._filenames[i] for i in current_ids]
        #     class_id = [self._class_id[i] for i in current_ids]
        #     sampled_embeddings, sampled_captions = \
        #         self.sample_embeddings(self._embeddings[current_ids],
        #                                filenames, class_id, window)

        sampled_embeddings = self._embeddings[current_ids]
        sampled_captions = ['no caption'] * sampled_embeddings.shape[0]

        sampled_images, sampled_embeddings = self.transform(sampled_images, sampled_embeddings)
        sampled_wrong_images, _ = self.transform(sampled_wrong_images)

        sampled_images = sampled_images * (2. / 255) - 1.
        sampled_wrong_images = sampled_wrong_images * (2. / 255) - 1.

        ret_list = list([sampled_images])
        ret_list.append(sampled_wrong_images)
        ret_list.append(sampled_embeddings)
        ret_list.append(sampled_captions)

        if self._labels is not None:
            ret_list.append(self._labels[current_ids])
        else:
            ret_list.append(None)

        return ret_list

    def next_batch_test(self, batch_size, start):
        if (start + batch_size) > self._num_examples:
            end = self._num_examples
            start = end - batch_size
        else:
            end = start + batch_size

        sampled_images = self._images[start:end]
        sampled_images = sampled_images.astype(np.float32)
        sampled_embeddings = self._embeddings[start:end]
        sampled_images, sampled_embeddings = self.transform(sampled_images, sampled_embeddings, jitter=False)

        sampled_images = sampled_images * (2.0 / 255.0) - 1.0

        # sampled_captions = []
        # sampled_filenames = self._filenames[start:end]
        # sampled_class_id = self._class_id[start:end]
        # for i in range(len(sampled_filenames)):
        #     captions = self.readCaptions(sampled_filenames[i], sampled_class_id[i])
        #     print(captions)
        #     sampled_captions.append(captions)

        # for i in range(np.minimum(max_captions, embedding_num)):
        #     batch = sampled_embeddings[:, i, :]
        #     sampled_embeddings_batchs.append(np.squeeze(batch))

        return sampled_images, sampled_embeddings, self._saveIDs[start:end]


class TextDataset(object):
    def __init__(self, workdir, embedding_type, hr_lr_ratio):
        lr_imsize = 64
        self.hr_lr_ratio = hr_lr_ratio
        # if self.hr_lr_ratio == 1:
        #     self.image_filename = '/76images_flying.pickle'
        # elif self.hr_lr_ratio == 4:
        #     self.image_filename = '/304images_flying.pickle'

        self.image_shape = [lr_imsize * self.hr_lr_ratio,
                            lr_imsize * self.hr_lr_ratio, 3]
        self.image_dim = self.image_shape[0] * self.image_shape[1] * 3
        self.embedding_shape = None
        self.train = None
        self.train2 = None
        self.test = None
        self.test2 = None
        self.workdir = workdir
        # if embedding_type == 'cnn-rnn':
        #     # self.embedding_filename = '/char-CNN-RNN-embeddings.pickle'
        #     self.embedding_filename = '/sketches_flying.pickle'
        # elif embedding_type == 'skip-thought':
        #     self.embedding_filename = '/skip-thought-embeddings.pickle'

    def get_data(self, pickle_path, subset=None, aug_flag=True, animated=""):
        with open(pickle_path + '/76images_flying_{}.pickle'.format(subset), 'rb') as f:
            images = pickle.load(f)
            images = images[0:10]
            images = np.array(images)
            print('images: ', images.shape)

        with open(pickle_path + '/sketches_flying_{}{}.pickle'.format(subset, animated), 'rb') as f:
            embeddings = pickle.load(f)
            embeddings = embeddings[0:10]
            embeddings = np.array(embeddings)
            embeddings = np.expand_dims(embeddings, axis=3)
            self.embedding_shape = [self.image_shape[0], self.image_shape[0], 1]
            print('embeddings: ', embeddings.shape)

        with open(pickle_path + '/filenames_flying_{}.pickle'.format(subset), 'rb') as f:
            list_filenames = pickle.load(f)
            list_filenames = list_filenames[0:10]
            print('list_filenames: ', len(list_filenames), list_filenames[0])

        with open(pickle_path + '/class_info_flying_{}.pickle'.format(subset), 'rb') as f:
            class_id = pickle.load(f)
            class_id = class_id[0:10]
            # class_id = None

        return Dataset(images, self.image_shape[0], embeddings,
                       list_filenames, self.workdir, None,
                       aug_flag, class_id)
