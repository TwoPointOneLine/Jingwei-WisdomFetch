import logoDark from '../../../../assets/logo-dark.png'
import logoLight from '../../../../assets/logo-light.png'
import Icon from '../../../../components/Icon'

/** 左侧栏头部：横版 logo（按主题切换）+ 右侧返回对话按钮 */
function SidebarHead({ onBack }: { onBack: () => void }) {
  return (
    <div className="sidebar-head">
      <div className="brand-horizontal" title="精卫 WisdomFetch">
        <img className="brand-h-dark" src={logoDark} alt="精卫 WisdomFetch" />
        <img className="brand-h-light" src={logoLight} alt="精卫 WisdomFetch" />
      </div>
      <button className="kb-back-btn" onClick={onBack} title="返回对话">
        <Icon name="arrow-left" size={14} />
        <span>返回</span>
      </button>
    </div>
  )
}

export { SidebarHead }
