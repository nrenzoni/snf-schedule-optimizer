
function debugSet<T>(label: string, set: (v: T | ((p: T) => T)) => void) {
    return (v: T | ((p: T) => T)) => {
        console.log(`[SET] ${label}`);
        console.trace(); // shows caller
        set(v);
    };
}
