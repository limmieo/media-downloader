import React, { useState } from 'react';
import {
    Stack,
    Text,
    TextField,
    Button,
    ChoiceGroup,
    IChoiceGroupOption,
    ProgressIndicator,
    MessageBar,
    MessageBarType,
    Icon,
    AnimationStyles,
    Checkbox,
    Spinner,
    SpinnerSize
} from '@fluentui/react';
import { useDispatch, useSelector } from 'react-redux';
import { convertVideo, downloadYouTube, downloadTikTok } from '../store/actions';

const App = () => {
    const dispatch = useDispatch();
    const [selectedTab, setSelectedTab] = useState('convert');
    const [videoUrl, setVideoUrl] = useState('');
    const [inputFile, setInputFile] = useState(null);
    const [outputFormat, setOutputFormat] = useState('mp4');
    const [progress, setProgress] = useState(0);
    const [message, setMessage] = useState(null);
    const [copyrightChecked, setCopyrightChecked] = useState(false);
    const [copyrightStatus, setCopyrightStatus] = useState('unverified'); // 'unverified', 'checking', 'verified', 'checking'
    const [isDownloading, setIsDownloading] = useState(false);

    const handleConvert = async () => {
        if (!inputFile) {
            setMessage({
                type: MessageBarType.error,
                text: 'Please select an input file'
            });
            return;
        }

        setMessage({
            type: MessageBarType.info,
            text: 'Converting video...'
        });

        try {
            await dispatch(convertVideo({
                inputPath: inputFile.path,
                outputPath: inputFile.path.replace(/\.[^/.]+$/, `.mp4`)
            }));
            
            setMessage({
                type: MessageBarType.success,
                text: 'Conversion complete!'
            });
        } catch (error) {
            setMessage({
                type: MessageBarType.error,
                text: 'Error converting video: ' + error.message
            });
        }
    };

    const checkCopyright = async (url) => {
        if (!url) return false;
        
        setCopyrightStatus('checking');
        try {
            const result = await window.electron.media.youtube.checkCopyright(url);
            const isVerified = result?.isCopyrightSafe || false;
            setCopyrightStatus(isVerified ? 'verified' : 'unverified');
            return isVerified;
        } catch (error) {
            console.error('Copyright check failed:', error);
            setCopyrightStatus('unverified');
            return false;
        }
    };

    const extractVideoId = (url) => {
        try {
            const urlObj = new URL(url);
            if (urlObj.hostname.includes('youtu.be')) {
                return urlObj.pathname.slice(1);
            }
            return urlObj.searchParams.get('v') || url.split('v=')[1]?.split('&')[0];
        } catch (e) {
            return null;
        }
    };

    const handleYouTubeDownload = async () => {
        if (!videoUrl) {
            setMessage({
                type: MessageBarType.error,
                text: 'Please enter a YouTube URL',
                dismissButtonAriaLabel: 'Close',
                onDismiss: () => setMessage(null)
            });
            return;
        }

        const videoId = extractVideoId(videoUrl);
        if (!videoId) {
            setMessage({
                type: MessageBarType.error,
                text: 'Invalid YouTube URL. Please enter a valid URL in one of these formats:\n- https://www.youtube.com/watch?v=VIDEO_ID\n- https://youtu.be/VIDEO_ID',
                dismissButtonAriaLabel: 'Close',
                onDismiss: () => setMessage(null)
            });
            return;
        }

        // Check copyright if not already verified
        if (!copyrightChecked) {
            setMessage({
                type: MessageBarType.info,
                text: 'Verifying copyright status...',
                dismissButtonAriaLabel: 'Close'
            });
            
            try {
                const isVerified = await checkCopyright(videoUrl);
                if (!isVerified) {
                    setMessage({
                        type: MessageBarType.warning,
                        text: 'Please verify copyright status before downloading',
                        dismissButtonAriaLabel: 'Close',
                        onDismiss: () => setMessage(null)
                    });
                    return;
                }
                setCopyrightChecked(true);
            } catch (error) {
                console.error('Copyright check failed:', error);
                setMessage({
                    type: MessageBarType.error,
                    text: 'Failed to verify copyright status. Please try again.',
                    dismissButtonAriaLabel: 'Close',
                    onDismiss: () => setMessage(null)
                });
                return;
            }
        }

        setIsDownloading(true);
        setProgress(0);
        setMessage({
            type: MessageBarType.info,
            text: 'Preparing download...',
            dismissButtonAriaLabel: 'Close'
        });

        try {
            // Set up progress listener
            const removeProgressListener = window.electron.onProgress((progress) => {
                setProgress(progress.percent);
                setMessage({
                    type: MessageBarType.info,
                    text: `Downloading... ${Math.round(progress.percent)}%`
                });
            });

            // Start the download
            // Show initial download message
            setMessage({
                type: MessageBarType.info,
                text: 'Starting download...',
                dismissButtonAriaLabel: 'Close'
            });

            try {
                const result = await window.electron.downloadYoutube({ 
                    url: videoUrl, 
                    format: outputFormat 
                });
                
                if (result && result.success) {
                    setMessage({
                        type: MessageBarType.success,
                        text: 'Download completed successfully!',
                        dismissButtonAriaLabel: 'Close',
                        onDismiss: () => setMessage(null)
                    });

                    // Open the download folder
                    try {
                        await window.electron.shell.showItemInFolder(result.outputPath);
                    } catch (folderError) {
                        console.warn('Could not open download folder:', folderError);
                        // Don't fail the download if we can't open the folder
                    }
                } else {
                    throw new Error('Download completed but no success flag was returned');
                }
            } catch (error) {
                console.error('Download failed:', error);
                
                // Default error message
                let errorMessage = 'An error occurred while downloading the video. Please try again.';
                
                // More specific error messages based on the error
                if (error.message.includes('Requested format is not available')) {
                    errorMessage = 'The requested video format is not available. Try a different format or video.';
                } else if (error.message.includes('Video unavailable') || 
                          error.message.includes('This video is unavailable')) {
                    errorMessage = 'This video is not available. It may have been removed, made private, or is not available in your country.';
                } else if (error.message.includes('Private video')) {
                    errorMessage = 'This video is private and cannot be downloaded.';
                } else if (error.message.includes('age restricted') || 
                          error.message.includes('Sign in to confirm your age')) {
                    errorMessage = 'This video is age-restricted and cannot be downloaded.';
                } else if (error.message.includes('timed out')) {
                    errorMessage = 'The download timed out. Please check your internet connection and try again.';
                } else if (error.message.includes('copyright')) {
                    errorMessage = 'Unable to verify copyright status for this video.';
                } else if (error.message.includes('Invalid YouTube URL')) {
                    errorMessage = 'The YouTube URL is not valid. Please check the URL and try again.';
                }
                
                setMessage({
                    type: MessageBarType.error,
                    text: errorMessage,
                    dismissButtonAriaLabel: 'Close',
                    onDismiss: () => setMessage(null)
                });
            } finally {
                setIsDownloading(false);
                setProgress(0);
            }
        } catch (error) {
            console.error('Download error:', error);
            
            // Default error message
            let errorMessage = 'An error occurred while downloading the video. Please try again.';
            
            // More specific error messages based on the error
            if (error.message.includes('Requested format is not available')) {
                errorMessage = 'The requested video format is not available. Try a different format or video.';
            } else if (error.message.includes('Video unavailable') || 
                      error.message.includes('This video is unavailable')) {
                errorMessage = 'This video is not available. It may have been removed, made private, or is not available in your country.';
            } else if (error.message.includes('Private video')) {
                errorMessage = 'This video is private and cannot be downloaded.';
            } else if (error.message.includes('age restricted') || 
                      error.message.includes('Sign in to confirm your age')) {
                errorMessage = 'This video is age-restricted and cannot be downloaded.';
            } else if (error.message.includes('timed out')) {
                errorMessage = 'The download timed out. Please check your internet connection and try again.';
            } else if (error.message.includes('copyright')) {
                errorMessage = 'Unable to verify copyright status for this video.';
            } else if (error.message.includes('Invalid YouTube URL')) {
                errorMessage = 'The YouTube URL is not valid. Please check the URL and try again.';
            }
            
            setMessage({
                type: MessageBarType.error,
                text: errorMessage,
                dismissButtonAriaLabel: 'Close',
                onDismiss: () => setMessage(null)
            });
        }
    };

    const handleTikTokDownload = async () => {
        if (!videoUrl) {
            setMessage({
                type: MessageBarType.error,
                text: 'Please enter a TikTok URL'
            });
            return;
        }

        setMessage({
            type: MessageBarType.info,
            text: 'Downloading TikTok video...'
        });

        try {
            await dispatch(downloadTikTok({
                url: videoUrl
            }));
            
            setMessage({
                type: MessageBarType.success,
                text: 'Download complete!'
            });
        } catch (error) {
            setMessage({
                type: MessageBarType.error,
                text: 'Error downloading video: ' + error.message
            });
        }
    };

    const formatOptions = [
        { key: 'mp4', text: 'MP4 (Video)' },
        { key: 'mp3', text: 'MP3 (Audio)' }
    ];

    return (
        <Stack
            styles={{ root: { padding: '20px', height: '100vh' } }}
            tokens={{ childrenGap: 20 }}
            verticalAlign="stretch"
        >
            <Stack.Item align="center">
                <Icon iconName="Video" styles={{ root: { fontSize: '48px', color: '#0078D4' } }} />
                <Text variant="xxLargePlus" styles={{ root: { marginTop: '10px' } }}>
                    Video Converter & Downloader
                </Text>
            </Stack.Item>

            <Stack horizontal horizontalAlign="center" tokens={{ childrenGap: 20 }}>
                <Button
                    text="Convert Video"
                    onClick={() => setSelectedTab('convert')}
                    styles={{
                        root: {
                            backgroundColor: selectedTab === 'convert' ? '#0078D4' : 'transparent',
                            color: selectedTab === 'convert' ? 'white' : '#0078D4',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '8px 20px',
                            ':hover': {
                                backgroundColor: selectedTab === 'convert' ? '#005A9E' : 'transparent',
                                color: 'white'
                            }
                        }
                    }}
                />
                <Button
                    text="YouTube"
                    onClick={() => setSelectedTab('youtube')}
                    styles={{
                        root: {
                            backgroundColor: selectedTab === 'youtube' ? '#0078D4' : 'transparent',
                            color: selectedTab === 'youtube' ? 'white' : '#0078D4',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '8px 20px',
                            ':hover': {
                                backgroundColor: selectedTab === 'youtube' ? '#005A9E' : 'transparent',
                                color: 'white'
                            }
                        }
                    }}
                />
                <Button
                    text="TikTok"
                    onClick={() => setSelectedTab('tiktok')}
                    styles={{
                        root: {
                            backgroundColor: selectedTab === 'tiktok' ? '#0078D4' : 'transparent',
                            color: selectedTab === 'tiktok' ? 'white' : '#0078D4',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '8px 20px',
                            ':hover': {
                                backgroundColor: selectedTab === 'tiktok' ? '#005A9E' : 'transparent',
                                color: 'white'
                            }
                        }
                    }}
                />
            </Stack>

            <Stack.Item grow>
                {selectedTab === 'convert' && (
                    <Stack tokens={{ childrenGap: 20 }}>
                        <input
                            type="file"
                            id="fileInput"
                            style={{ display: 'none' }}
                            onChange={(e) => setInputFile(e.target.files?.[0])}
                        />
                        <Button
                            text="Select Video File"
                            onClick={() => document.getElementById('fileInput')?.click()}
                            styles={{
                                root: {
                                    backgroundColor: '#0078D4',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    ':hover': {
                                        backgroundColor: '#005A9E'
                                    }
                                }
                            }}
                        />
                        <ChoiceGroup
                            options={formatOptions}
                            selectedKey={outputFormat}
                            onChange={(e, option) => setOutputFormat(option.key)}
                        />
                        <Button
                            text="Convert"
                            onClick={handleConvert}
                            styles={{
                                root: {
                                    backgroundColor: '#0078D4',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    ':hover': {
                                        backgroundColor: '#005A9E'
                                    }
                                }
                            }}
                        />
                    </Stack>
                )}

                {selectedTab === 'youtube' && (
                    <Stack tokens={{ childrenGap: 20 }}>
                        <TextField
                            placeholder="Enter YouTube URL"
                            value={videoUrl}
                            onChange={(e, newValue) => setVideoUrl(newValue || '')}
                        />
                        <div style={{ margin: '15px 0' }}>
                            <Label>Output Format:</Label>
                            <Dropdown
                                selectedKey={downloadFormat}
                                onChange={(e, item) => setDownloadFormat(item.key)}
                                placeholder="Select format"
                                options={[
                                    { key: 'mp4', text: 'MP4 (Video)' },
                                    { key: 'mp3', text: 'MP3 (Audio Only)' }
                                ]}
                                disabled={isDownloading}
                            />
                        </div>

                        <div style={{ margin: '15px 0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                                <Checkbox 
                                    label="I verify that I have the right to use this content"
                                    checked={copyrightChecked}
                                    onChange={async (ev, checked) => {
                                        if (checked) {
                                            setCopyrightStatus('checking');
                                            try {
                                                const isVerified = await checkCopyright(videoUrl);
                                                setCopyrightStatus(isVerified ? 'verified' : 'unverified');
                                                setCopyrightChecked(isVerified);
                                                
                                                if (!isVerified) {
                                                    setMessage({
                                                        type: MessageBarType.warning,
                                                        text: 'Unable to verify copyright. Please ensure you have the right to use this content.',
                                                        dismissButtonAriaLabel: 'Close',
                                                        onDismiss: () => setMessage(null)
                                                    });
                                                }
                                            } catch (error) {
                                                console.error('Copyright check failed:', error);
                                                setCopyrightStatus('unverified');
                                                setCopyrightChecked(false);
                                                setMessage({
                                                    type: MessageBarType.error,
                                                    text: 'Failed to verify copyright. Please try again.',
                                                    dismissButtonAriaLabel: 'Close',
                                                    onDismiss: () => setMessage(null)
                                                });
                                            }
                                        } else {
                                            setCopyrightChecked(false);
                                            setCopyrightStatus('unverified');
                                        }
                                    }}
                                    disabled={isDownloading || !videoUrl}
                                    styles={{
                                        root: { margin: 0 },
                                        text: { fontWeight: 'normal' },
                                        checkbox: { marginTop: 0 }
                                    }}
                                />
                                {copyrightStatus === 'checking' && (
                                    <Spinner size={SpinnerSize.small} style={{ marginLeft: 10 }} />
                                )}
                                {copyrightStatus === 'verified' && (
                                    <Icon 
                                        iconName="CheckMark" 
                                        style={{ 
                                            color: 'green', 
                                            marginLeft: 10,
                                            fontSize: 16,
                                            fontWeight: 'bold'
                                        }} 
                                    />
                                )}
                                {copyrightStatus === 'unverified' && (
                                    <Icon 
                                        iconName="ErrorBadge" 
                                        style={{ 
                                            color: 'orange', 
                                            marginLeft: 10,
                                            fontSize: 16
                                        }} 
                                    />
                                )}
                            </div>
                            <Text variant="small" styles={{ root: { color: theme.palette.neutralSecondary, marginLeft: 26 } }}>
                                {copyrightChecked 
                                    ? 'Copyright verified. You may proceed with the download.'
                                    : 'Please verify that you have the right to use this content before downloading.'}
                            </Text>
                        </div>

                        <Button
                            text="Download"
                            onClick={handleYouTubeDownload}
                            styles={{
                                root: {
                                    backgroundColor: '#0078D4',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    ':hover': {
                                        backgroundColor: '#005A9E'
                                    }
                                }
                            }}
                        />
                    </Stack>
                )}

                {selectedTab === 'tiktok' && (
                    <Stack tokens={{ childrenGap: 20 }}>
                        <TextField
                            placeholder="Enter TikTok URL"
                            value={videoUrl}
                            onChange={(e, newValue) => setVideoUrl(newValue || '')}
                        />
                        <Button
                            text="Download"
                            onClick={handleTikTokDownload}
                            styles={{
                                root: {
                                    backgroundColor: '#0078D4',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    ':hover': {
                                        backgroundColor: '#005A9E'
                                    }
                                }
                            }}
                        />
                    </Stack>
                )}
            </Stack.Item>

            {message && (
                <MessageBar
                    messageBarType={message.type}
                    onDismiss={() => setMessage(null)}
                    dismissButtonAriaLabel="Close"
                >
                    {message.text}
                </MessageBar>
            )}
        </Stack>
    );
};

export default App;
