const hooks = new Map();

const normalizeValue = (value) => {
    if (value == null) {
        return '';
    }

    if (typeof value === 'string') {
        return value;
    }

    return String(value);
};

const DOMPurifyShim = {
    sanitize(value) {
        return normalizeValue(value);
    },
    addHook(name, callback) {
        if (typeof name !== 'string' || typeof callback !== 'function') {
            return;
        }

        const callbacks = hooks.get(name) || [];
        callbacks.push(callback);
        hooks.set(name, callbacks);
    },
    removeHook(name) {
        hooks.delete(name);
    },
    removeHooks(name) {
        hooks.delete(name);
    },
    removeAllHooks() {
        hooks.clear();
    },
    isSupported: true,
};

export default DOMPurifyShim;
