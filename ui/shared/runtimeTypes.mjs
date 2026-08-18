export const isRuntimeString = (value) => String(value) === value;

export const isRuntimeNumber = (value) => Object.is(Number(value), value);

export const isRuntimeFunction = (value) => value instanceof Function;
