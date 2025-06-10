export const useFormatters = () => {
    /**
     * Formats a message cost value to a string with specified decimal places.
     * @param value - The cost value to format.
     * @param decimalPlaces - The number of decimal places to include in the formatted string (default is 2).
     * @return A string representation of the cost value formatted to the specified number of decimal places.
     * If the value is NaN, it returns '0.00'.
     * If the value is 0 when cropped to the specified decimal places, it returns '< 0.[nx0]1$'.
     * Else it returns the value formatted to the specified number of decimal places.
     */
    const formatMessageCost = (value: number, decimalPlaces: number = 4): string => {
        if (isNaN(value)) {
            return `0.${'0'.repeat(decimalPlaces)}$`;
        }
        const croppedValue = parseFloat(value.toFixed(decimalPlaces));
        if (croppedValue === 0) {
            return `< 0.${'0'.repeat(decimalPlaces - 1)}1$`;
        }
        return croppedValue.toFixed(decimalPlaces) + '$';
    };

    return {
        formatMessageCost,
    };
};
