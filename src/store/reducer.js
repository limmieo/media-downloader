const initialState = {
    conversionStatus: 'idle',
    conversionProgress: 0,
    conversionError: null,
    downloadStatus: 'idle',
    downloadProgress: 0,
    downloadError: null,
};

const reducer = (state = initialState, action) => {
    switch (action.type) {
        case 'CONVERT_REQUEST':
            return {
                ...state,
                conversionStatus: 'processing',
                conversionProgress: 0,
                conversionError: null,
            };
        case 'CONVERT_SUCCESS':
            return {
                ...state,
                conversionStatus: 'success',
                conversionProgress: 100,
            };
        case 'CONVERT_ERROR':
            return {
                ...state,
                conversionStatus: 'error',
                conversionError: action.payload,
            };
        case 'DOWNLOAD_REQUEST':
            return {
                ...state,
                downloadStatus: 'processing',
                downloadProgress: 0,
                downloadError: null,
            };
        case 'DOWNLOAD_SUCCESS':
            return {
                ...state,
                downloadStatus: 'success',
                downloadProgress: 100,
            };
        case 'DOWNLOAD_ERROR':
            return {
                ...state,
                downloadStatus: 'error',
                downloadError: action.payload,
            };
        default:
            return state;
    }
};

export { reducer };
