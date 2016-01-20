import py
from click import echo
from operator import attrgetter

from .dotfile import Dotfile
from .exceptions import DotfileException, TargetIgnored
from .exceptions import NotRootedInHome, InRepository, IsDirectory


class Repository(object):
    """A repository is a directory that contains dotfiles.

    :param repodir: the location of the repository directory
    :param homedir: the location of the home directory (primarily for testing)
    :param ignore:  a list of targets to ignore
    :param dot:     wether to preserve the target's leading dot
    """

    homedir = py.path.local('~/', expanduser=True)

    def __init__(self, repodir, homedir=homedir, ignore=[], dot=True):
        self.repodir = py.path.local(repodir).ensure_dir()
        self.homedir = py.path.local(homedir)
        self.ignore = ignore
        self.dot = dot

    def __str__(self):
        """Return human-readable repository contents."""
        return ''.join('%s\n' % item for item in self.contents()).rstrip()

    def __repr__(self):
        return '<Repository %r>' % self.repodir

    def _target_to_name(self, target):
        """Return the expected symlink for the given repository target."""
        relpath = self.repodir.bestrelpath(target)
        if self.dot:
            return self.homedir.join(relpath)
        else:
            return self.homedir.join('.%s' % relpath)

    def _name_to_target(self, name):
        """Return the expected repository target for the given symlink."""
        relpath = self.homedir.bestrelpath(name)
        if self.dot:
            return self.repodir.join(relpath)
        else:
            return self.repodir.join(relpath[1:])

    def _dotfile(self, name):
        """Return a valid dotfile for the given path."""
        target = self._name_to_target(name)

        if not name.fnmatch('%s/*' % self.homedir):
            raise NotRootedInHome(name)
        if name.fnmatch('%s/*' % self.repodir):
            raise InRepository(name)
        if target.basename in self.ignore:
            raise TargetIgnored(name)
        if name.check(dir=1):
            raise IsDirectory(name)

        return Dotfile(name, target)

    def _contents(self, dir):
        """Return all unignored files contained below a directory."""
        def filter(node):
            return node.check(dir=0) and node.basename not in self.ignore

        def recurse(node):
            return node.basename not in self.ignore

        return dir.visit(filter, recurse)

    def dotfiles(self, paths):
        """Return a collection of dotfiles given a list of paths.

        This function takes a list of paths where each path can be a file or a
        directory.  Each directory is recursively expaned into file paths.
        Once the list is converted into only files, dotifles are constructed
        for each path in the set.  This set of dotfiles is returned to the
        caller.
        """
        paths = list(set(map(py.path.local, paths)))

        for path in paths:
            if path.check(dir=1):
                paths.extend(self._contents(path))
                paths.remove(path)

        def construct(path):
            try:
                return self._dotfile(path)
            except DotfileException as err:
                echo(err)
                return None

        return [d for d in map(construct, paths) if d is not None]

    def contents(self):
        """Return a list of dotfiles for each file in the repository."""
        def construct(target):
            return Dotfile(self._target_to_name(target), target)

        contents = self._contents(self.repodir)
        return sorted(map(construct, contents), key=attrgetter('name'))

    def prune(self):
        """Remove any empty directories in the repository.

        After a remove operation, there may be empty directories remaining.
        The Dotfile class has no knowledge of other dotfiles in the repository,
        so pruning must take place explicitly after such operations occur.
        """
        def filter(node):
            return node.check(dir=1) and node.basename not in self.ignore

        def recurse(node):
            return node.basename not in self.ignore

        for dir in self.repodir.visit(filter, recurse):
            if not len(dir.listdir()):
                dir.remove()
