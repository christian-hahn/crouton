from threading import Lock


class Namespace:

    def __init__(self):
        self.types = {}
        # Instances by [instance id]
        self._instances = {}
        # Instances by [name]
        self._instances_by_name = {}
        # Reference counts by [instance id][owner]
        self._ref_counts = {}
        self._lock = Lock()

    def __getitem__(self, key):
        """Get an instance by id or name.

        Args:
            key (int, str): instance id or name

        Returns:
            object: instance
        """
        return self._instances[key] if isinstance(key, int) else \
            self._instances_by_name[key]

    def __contains__(self, item):
        """Is instance in namespace.

        Args:
            item (int, str): instance id or name

        Returns:
            bool: exists in namespace
        """
        return item in self._instances if isinstance(item, int) else \
            item in self._instances_by_name

    def __enter__(self):
        """On enter, lock namespace."""
        self._lock.acquire()
        return self

    def __exit__(self, type, value, traceback):
        """On exit, unlock namespace."""
        self._lock.release()

    def add(self, instance, inst_id, owner, name=None):
        """Add an instance and acquire reference.

        Args:
            instance (object): instance
            inst_id (int): instance id
            owner (object): owner
        """
        owner = id(owner)
        if inst_id in self._instances:
            ref_counts = self._ref_counts[inst_id]
            if owner in ref_counts:
                ref_counts[owner] += 1
            else:
                ref_counts[owner] = 1
        else:
            self._instances[inst_id] = instance
            self._ref_counts[inst_id] = {owner: 1}
        if not name is None:
            self._instances_by_name[name] = instance

    def acquire(self, inst_id, owner):
        """Acquire a reference to an instance.

        Args:
            inst_id (int): instance id
            owner (object): owner
        """
        owner = id(owner)
        ref_counts = self._ref_counts[inst_id]
        if owner in ref_counts:
            ref_counts[owner] += 1
        else:
            ref_counts[owner] = 1

    def release(self, inst_id, owner):
        """Release a reference to an instance.

        Args:
            inst_id (int): instance id
            owner (object): owner

        Returns:
            bool: owner released in instance
        """
        owner = id(owner)
        ref_counts = self._ref_counts[inst_id]
        ref_counts[owner] -= 1
        if ref_counts[owner] < 1:
            del ref_counts[owner]
            if not ref_counts:
                del self._ref_counts[inst_id]
                del self._instances[inst_id]
            return True
        return False

    def release_all(self, inst_ids, owner):
        """Release all references to a set of instances.

        Args:
            inst_ids (set): instance id
            owner (object): owner
        """
        owner = id(owner)
        for inst_id in inst_ids:
            ref_counts = self._ref_counts[inst_id]
            del ref_counts[owner]
            if not ref_counts:
                del self._ref_counts[inst_id]
                del self._instances[inst_id]
