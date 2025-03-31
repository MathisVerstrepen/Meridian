module.exports = {
    plugins: [
        'prettier-plugin-tailwindcss',
        'prettier-plugin-classnames',
        'prettier-plugin-merge',
    ],
    tailwindFunctions: ['cn'],
    semi: true,
    trailingComma: 'all',
    singleQuote: true,
    printWidth: 80,
    tabWidth: 4,
    overrides: [
        {
            files: ['*.vue'],
            options: {
                printWidth: 100,
            },
        },
    ],
};
