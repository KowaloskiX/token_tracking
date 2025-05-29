import React from 'react';
import styled, { keyframes } from 'styled-components';

const jumpAnimation = keyframes`
  0% {
    transform: translateY(0px);
    opacity: 1;
  }
  28% {
    transform: translateY(-3px);
    opacity: 0.3;
  }
  42% {
    transform: translateY(0px);
    opacity: 0.6;
  }
`;

const ThinkingContainer = styled.div`
  display: flex;
  gap: 2px;
  align-items: center;
  height: 20px;
`;

const Character = styled.span<{ delay: number }>`
  display: inline-block;
  animation: ${jumpAnimation} 1.5s infinite ease-in-out;
  animation-delay: ${props => props.delay}ms;
  margin-left: -0.05em;
`;

const Thinking = (props: { text: string }) => {
    return (
        <ThinkingContainer>
            {props.text.split('').map((char, i) => (
                <Character key={i} delay={250 + (i * 100)}>
                    {char}
                </Character>
            ))}
        </ThinkingContainer>
    );
};

export default Thinking;