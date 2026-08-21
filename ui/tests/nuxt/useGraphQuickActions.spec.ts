import { describe, expect, it } from 'vitest';

import {
    classifyQuickActionTarget,
    isQuickActionEditable,
    resolveQuickActionGestureTarget,
} from '@/composables/useGraphQuickActions';
import {
    createAddQuickActionMetadata,
    createQuickWorkflowActionMetadata,
} from '@/composables/useGraphQuickActionMenu';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { WheelSlot } from '@/types/settings';

describe('graph quick-action target classification', () => {
    it('propagates block colors into Add node action metadata', () => {
        const block = {
            id: 'prompt-text',
            name: 'Prompt Text',
            icon: 'prompt-icon',
            color: 'var(--color-ember-glow)',
        };

        expect(createAddQuickActionMetadata(block, false)).toEqual({
            id: 'add-prompt-text',
            label: 'Prompt Text',
            icon: 'prompt-icon',
            accentColor: 'var(--color-ember-glow)',
            locked: false,
        });
        expect(createAddQuickActionMetadata({ ...block, color: undefined }, true)).toMatchObject({
            label: 'Prompt Text (Premium)',
            accentColor: undefined,
            locked: true,
        });
    });

    it('uses the configured workflow main block icon and color in informative metadata', () => {
        const slot: WheelSlot = {
            name: 'Summarize first',
            mainBloc: NodeTypeEnum.ROUTING,
            options: [NodeTypeEnum.PROMPT],
        };
        const routingBlock = {
            name: 'Routing',
            icon: 'routing-icon',
            color: 'var(--color-slate-blue)',
        };

        expect(
            createQuickWorkflowActionMetadata(
                slot,
                NodeCategoryEnum.CONTEXT,
                'source',
                2,
                (nodeType) => (nodeType === NodeTypeEnum.ROUTING ? routingBlock : undefined),
            ),
        ).toEqual({
            id: 'workflow-context-source-2',
            label: 'Context output handle · Routing node',
            icon: 'routing-icon',
            accentColor: 'var(--color-slate-blue)',
            compactHandle: { category: 'context', direction: 'source' },
        });
    });

    it('resolves nodes before pane and distinguishes edges and canvas', () => {
        const container = document.createElement('div');
        const pane = document.createElement('div');
        pane.className = 'vue-flow__pane';
        const node = document.createElement('div');
        node.className = 'vue-flow__node';
        node.dataset.id = 'node-1';
        const nodeChild = document.createElement('span');
        node.append(nodeChild);
        const edge = document.createElement('path');
        edge.classList.add('vue-flow__edge');
        pane.append(node, edge);
        container.append(pane);

        expect(classifyQuickActionTarget(nodeChild, container)).toEqual({
            kind: 'node',
            nodeId: 'node-1',
        });
        expect(classifyQuickActionTarget(edge, container)).toEqual({ kind: 'edge' });
        expect(classifyQuickActionTarget(pane, container)).toEqual({ kind: 'canvas' });
    });

    it('bypasses editable descendants and unrelated controls', () => {
        const container = document.createElement('div');
        const input = document.createElement('input');
        const control = document.createElement('button');
        container.append(input, control);

        expect(isQuickActionEditable(input)).toBe(true);
        expect(classifyQuickActionTarget(input, container)).toEqual({ kind: 'ignored' });
        expect(classifyQuickActionTarget(control, container)).toEqual({ kind: 'ignored' });
    });

    it('ignores marked file-manager items without exempting their containing node', () => {
        const container = document.createElement('div');
        const node = document.createElement('div');
        node.className = 'vue-flow__node';
        node.dataset.id = 'file-node';
        const fileItem = document.createElement('div');
        fileItem.dataset.graphQuickActionsIgnore = '';
        const fileName = document.createElement('span');
        fileItem.append(fileName);
        const nodeSurface = document.createElement('div');
        node.append(fileItem, nodeSurface);
        container.append(node);

        const fileEvent = new MouseEvent('mousedown', { button: 2, bubbles: true });
        fileName.dispatchEvent(fileEvent);
        const nodeEvent = new MouseEvent('mousedown', { button: 2, bubbles: true });
        nodeSurface.dispatchEvent(nodeEvent);

        expect(classifyQuickActionTarget(fileName, container)).toEqual({ kind: 'ignored' });
        expect(resolveQuickActionGestureTarget(fileEvent, container)).toBeNull();
        expect(resolveQuickActionGestureTarget(nodeEvent, container)).toEqual({
            kind: 'node',
            nodeId: 'file-node',
        });
    });
});
