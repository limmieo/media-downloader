import { ipcRenderer } from 'electron';

export const convertVideo = (payload) => async (dispatch) => {
    try {
        await ipcRenderer.invoke('convertVideo', payload);
        dispatch({ type: 'CONVERT_SUCCESS' });
    } catch (error) {
        dispatch({ type: 'CONVERT_ERROR', payload: error.message });
    }
};

export const downloadYouTube = (payload) => async (dispatch) => {
    try {
        await ipcRenderer.invoke('downloadYouTube', payload);
        dispatch({ type: 'DOWNLOAD_YOUTUBE_SUCCESS' });
    } catch (error) {
        dispatch({ type: 'DOWNLOAD_YOUTUBE_ERROR', payload: error.message });
    }
};

export const downloadTikTok = (payload) => async (dispatch) => {
    try {
        await ipcRenderer.invoke('downloadTikTok', payload);
        dispatch({ type: 'DOWNLOAD_TIKTOK_SUCCESS' });
    } catch (error) {
        dispatch({ type: 'DOWNLOAD_TIKTOK_ERROR', payload: error.message });
    }
};
