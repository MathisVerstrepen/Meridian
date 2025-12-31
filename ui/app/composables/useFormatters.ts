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

    /**
     * Formats a model price value to a string representing the cost per million tokens.
     * @param price - The price value to format.
     * @return A string representation of the model price formatted as '$X.XX/M', where X is the price in millions.
     */
    const formatModelPrice = (price: number) => {
        return `$${(price * 1000000).toFixed(2)}/M`;
    };

    /**
     * Formats a context length value to a string with appropriate suffixes (K, M, B).
     * @param length - The context length value to format.
     * @return A string representation of the context length formatted with K for thousands, M for millions, and B for billions.
     */
    const formatContextLength = (length: number) => {
        if (length >= 1e9) {
            return `${(length / 1e9).toFixed(1)}B`;
        } else if (length >= 1e6) {
            return `${(length / 1e6).toFixed(1)}M`;
        } else if (length >= 1e3) {
            return `${(length / 1e3).toFixed(1)}K`;
        }
    };

    /**
     * Formats a file size value to a string with appropriate suffixes (B, KB, MB, GB).
     * @param size - The file size value to format.
     * @return A string representation of the file size formatted with B for bytes, KB for kilobytes, MB for megabytes, and GB for gigabytes.
     */
    const formatFileSize = (size: number) => {
        if (size >= 1073741824) {
            return `${(size / 1073741824).toFixed(1)} GB`;
        } else if (size >= 1048576) {
            return `${(size / 1048576).toFixed(1)} MB`;
        } else if (size >= 1024) {
            return `${(size / 1024).toFixed(1)} KB`;
        } else {
            return `${size} B`;
        }
    };

    return {
        formatMessageCost,
        formatModelPrice,
        formatContextLength,
        formatFileSize,
    };
};
