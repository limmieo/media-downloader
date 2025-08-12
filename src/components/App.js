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

    const handleYouTubeDownload = async () => {
        if (!videoUrl) {
            setMessage({
                type: MessageBarType.error,
                text: 'Please enter a YouTube URL'
            });
            return;
        }

        setMessage({
            type: MessageBarType.info,
            text: 'Downloading YouTube video...'
        });

        try {
            await dispatch(downloadYouTube({
                url: videoUrl,
                format: outputFormat
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

    const formatOptions: IChoiceGroupOption[] = [
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
                            onChange={(e, option) => setOutputFormat(option.key as string)}
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
                        <ChoiceGroup
                            options={formatOptions}
                            selectedKey={outputFormat}
                            onChange={(e, option) => setOutputFormat(option.key as string)}
                        />
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
