(function() {
    /**
     * 블록이 '고아' 상태인지 확인합니다. 고아 블록은 부모 블록에 연결되어야 하지만
     * 최상위 수준에 독립적으로 떨어져 있는 블록을 의미합니다 (예: '이전 블록' 또는 '출력' 연결이 있는 블록).
     * 스크립트를 시작하는 '모자 블록'은 고아 블록으로 간주하지 않습니다.
     * @param {Blockly.Block} block 확인할 블록.
     * @returns {boolean} 블록이 고아 상태이면 true를 반환합니다.
     */
    function isOrphan(block) {
        // 부모 블록에 연결된 블록의 경우, 부모가 고아인지 재귀적으로 확인합니다.
        const parent = block.getParent();
        if (parent) {
            return isOrphan(parent);
        }
        // 부모가 없는 경우, '이전' 또는 '출력' 연결이 있어야만 고아 블록으로 간주합니다.
        return !!(block.outputConnection || block.previousConnection);
    }

    /**
     * 유효한 실행 스택에 연결되지 않은 최상위 블록('고아 블록')을
     * 자동으로 비활성화하는 Blockly 플러그인입니다.
     * @param {Blockly.WorkspaceSvg} workspace 플러그인을 적용할 작업 공간.
     */
    function DisableTopBlocks(workspace) {
        this.workspace = workspace;
        this.changeListener = null; // 리스너 참조를 저장하기 위함
        this.oldPreconditionFn = null;
        this.oldCallbackFn = null;
    }

    /**
     * 플러그인을 초기화합니다. 컨텍스트 메뉴를 재정의하고,
     * 블록의 활성화/비활성화 상태를 관리하는 리스너를 추가합니다.
     */
    DisableTopBlocks.prototype.init = function() {
        // --- 컨텍스트 메뉴 재정의 ---
        const disableMenuItem = Blockly.ContextMenuRegistry.registry.getItem('blockDisable');
        if (!disableMenuItem) {
            console.warn("DisableTopBlocks: 컨텍스트 메뉴 항목 'blockDisable'을 찾을 수 없습니다.");
            return;
        }

        this.oldPreconditionFn = disableMenuItem.preconditionFn;
        disableMenuItem.preconditionFn = (scope) => {
            const block = scope.block;
            if (!block.isInFlyout && block.isEditable()) {
                if (!isOrphan(block)) {
                    return 'enabled';
                }
            }
            return 'hidden';
        };

        this.oldCallbackFn = disableMenuItem.callback;
        disableMenuItem.callback = (scope) => {
            if (this.oldCallbackFn) {
                this.oldCallbackFn(scope);
            }
            scope.block.userDisabled = !scope.block.isEnabled();
        };

        // --- 작업 공간 변경 리스너 ---
        this.changeListener = (event) => {
            // UI 이벤트(클릭, 뷰포트 변경 등)는 무시합니다.
            if (event.isUiEvent) {
                return;
            }
            
            // **수정된 부분**: 새로운 블록 생성 이벤트를 특별히 처리합니다.
            if (event.type === Blockly.Events.CREATE) {
                const block = this.workspace.getBlockById(event.blockId);
                if (block) {
                    // 저장된 상태에서 불러오는 것이 아니라, 도구상자에서 새로 가져온 블록인지 확인합니다.
                    // 새로 가져온 블록은 XML에 'disabled' 속성이 없습니다.
                    const isNewFromFlyout = event.xml.getAttribute('disabled') !== 'true';

                    if (isNewFromFlyout) {
                        block.userDisabled = false;
                        block.setEnabled(true);
                        // 새로 생성된 블록이 즉시 고아 블록으로 처리되는 것을 막기 위해 여기서 리스너를 종료합니다.
                        return;
                    }
                }
            }

            // 그 외 모든 이벤트(이동, 연결, 삭제, 불러오기 등)에 대해 모든 블록을 재평가합니다.
            const blocks = this.workspace.getAllBlocks(false);
            blocks.forEach((block) => {
                // userDisabled 속성이 정의되지 않은 경우(초기 상태), 현재 블록 상태를 기반으로 설정합니다.
                if (typeof block.userDisabled === 'undefined') {
                    block.userDisabled = !block.isEnabled();
                }

                if (isOrphan(block)) {
                    // 고아 블록은 사용자 설정과 관계없이 항상 비활성화합니다.
                    block.setEnabled(false);
                } else {
                    // 고아 블록이 아닌 경우, 사용자의 선택(`userDisabled`)에 따라 상태를 결정합니다.
                    block.setEnabled(!block.userDisabled);
                }
            });
        };
        this.workspace.addChangeListener(this.changeListener);
    };

    /**
     * 플러그인을 해제하고, 원래의 Blockly 기능을 복원하며 리스너를 정리합니다.
     */
    DisableTopBlocks.prototype.dispose = function() {
        const disableMenuItem = Blockly.ContextMenuRegistry.registry.getItem('blockDisable');
        if (disableMenuItem) {
            disableMenuItem.preconditionFn = this.oldPreconditionFn;
            disableMenuItem.callback = this.oldCallbackFn;
        }

        if (this.changeListener) {
            this.workspace.removeChangeListener(this.changeListener);
        }
    };

    // 플러그인을 전역적으로 사용할 수 있도록 내보냅니다.
    window.DisableTopBlocks = DisableTopBlocks;
})();

