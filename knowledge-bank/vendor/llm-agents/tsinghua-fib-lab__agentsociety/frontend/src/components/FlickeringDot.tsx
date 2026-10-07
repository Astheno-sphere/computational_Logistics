import React, { useState, useEffect } from 'react';

const FlickeringDot = ({
    width, height, borderRadius, backgroundColor, intervalMs
}: {
    width: string,
    height: string,
    borderRadius: string,
    backgroundColor: string
    intervalMs?: number
}) => {
    const [isFlickering, setIsFlickering] = useState(true);

    useEffect(() => {
        if (intervalMs !== undefined) {
            const interval = setInterval(() => {
                setIsFlickering(prev => !prev);
            }, intervalMs);
            return () => clearInterval(interval);
        }
    }, [intervalMs]);

    const dotStyle = {
        width: width,
        height: height,
        borderRadius: borderRadius,
        backgroundColor: isFlickering ? backgroundColor : 'transparent',
    };

    return (
        <div style={dotStyle}></div>
    );
}

export default FlickeringDot;