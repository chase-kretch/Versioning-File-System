#!/usr/bin/env python


# Chase Pholdee-Kretschmar, cpho632, 208579690

from __future__ import with_statement

import logging

import os
import sys
import errno
import shutil
import filecmp
import glob

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

class VersionFS(LoggingMixIn, Operations):
    def __init__(self):
        # get current working directory as place for versions tree
        self.root = os.path.join(os.getcwd(), '.versiondir')
        # check to see if the versions directory already exists
        if os.path.exists(self.root):
            print ('Version directory already exists.')
        else:
            print ('Creating version directory.')
            os.mkdir(self.root)

    # Helpers
    # =======

    def _full_path_latest_version(self, partial):  # Partial = path without versioning
        path = self._unversioned_path(partial)

        if os.path.isdir(path):
            return path
        if (partial.startswith(".")):
            return path # do not version hidden files
        
        return path + ".1"
    
    def _full_path_temp_file(self, partial):
        path = self._unversioned_path(partial)

        if os.path.isdir(path):
            return path
        if (partial.startswith(".")):
            return path # do not version hidden files
        
        return path + ".temp"        


    def _unversioned_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def _full_path(self, partial):
        # So i dont have to change full_path elsewhere
        return self._full_path_latest_version(partial)

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        # print ("access:", path, mode)
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        # print ("chmod:", path, mode)
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        # print ("chown:", path, uid, gid)
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        # print ("getattr:", path)
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        # print ("readdir:", path)
        full_path = self._full_path(path)
        paths = set()
        dirents = ['.', '..']
        if os.path.isdir(full_path):
            for filename in os.listdir(full_path):
                # In my versioning system, versions do not exceed .6 so no need to slice more than 2 characters
                if filename[:-2] in paths:
                    continue
                else:
                    paths.add(filename[:-2])
                    dirents.append(filename[:-2])
        for r in dirents:
            yield r

    def readlink(self, path):
        # print("READLINK")
        # print ("readlink:", path)
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        # print ("mknod:", path, mode, dev)
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        # print ("rmdir:", path)
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        # print ("mkdir:", path, mode)
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        # print ("statfs:", path)
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        # print ("unlink:", path)
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        # print ("symlink:", name, target)
        return os.symlink(target, self._full_path(name))

    def rename(self, old, new):
        # print ("rename:", old, new)
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        # print ("link:", target, name)
        return os.link(self._full_path(name), self._full_path(target))

    def utimens(self, path, times=None):
        # print ("utimens:", path, times)
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        print ('** open:', path, '**')
        full_path = self._full_path_latest_version(path)
        # Create temp file
        temp_full_path = self._full_path_temp_file(path)
        shutil.copyfile(full_path, temp_full_path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print ('** create:', path, '**')
        full_path = self._full_path_latest_version(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        print ('** read:', path, '**')
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        print ('** write:', path, '**')
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        print ('** truncate:', path, '**')
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        print ('** flush', path, '**')
        return os.fsync(fh)

    def release(self, path, fh):
        print ('** release', path, '**')
        full_path = self._full_path_latest_version(path)  # Version 1
        temp_full_path = self._full_path_temp_file(path)  # Version 2

        os.close(fh)

        if filecmp.cmp(full_path, temp_full_path, shallow=False):
            os.remove(temp_full_path)
            return
        
        v6_path = self._unversioned_path(path) + '.6'
        v5_path = self._unversioned_path(path) + '.5'
        v4_path = self._unversioned_path(path) + '.4'
        v3_path = self._unversioned_path(path) + '.3'
        v2_path = self._unversioned_path(path) + '.2'

        if os.path.isfile(v6_path):
            os.remove(v6_path)
        if os.path.isfile(v5_path):
            os.rename(v5_path, v6_path)
        if os.path.isfile(v4_path):
            os.rename(v4_path, v5_path)
        if os.path.isfile(v3_path):
            os.rename(v3_path, v4_path)
        if os.path.isfile(v2_path):
            os.rename(v2_path, v3_path)

        os.rename(temp_full_path, v2_path)



        
        


    def fsync(self, path, fdatasync, fh):
        print ('** fsync:', path, '**')
        return self.flush(path, fh)

def main(mountpoint):
    FUSE(VersionFS(), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1])
