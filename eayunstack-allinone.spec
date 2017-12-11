Name:		eayunstack-allinone
Version:	1.0
Release:	2%{?dist}
Summary:	EayunStack All-In-One VM Management Tool

Group:		Application
License:	GPL
URL:		http://www.eayun.com
Source0:	eayunstack-allinone-1.0.tgz

BuildRequires:	/bin/bash
BuildRequires:	python
Requires:	libvirt
Requires:	libvirt-python
Requires:	python
Requires:	python-netifaces

%description
EayunStack All-In-One Management Tool


%prep
%setup -q


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/eayunstack-allinone/
install -p -D -m 755 allinone.py %{buildroot}/opt/eayunstack-allinone/
install -p -D -m 755 operate.py %{buildroot}/opt/eayunstack-allinone/


%files
%doc
%attr(0755,root,root)/opt/eayunstack-allinone/


%changelog
* Mon Dec 5 2017 Armstrong Liu <vpbvmw651078@gmail.com> 1.0-2
- Cancel ext interface for allinone

* Thu Nov 2 2017 Ma Zhe	<zhe.ma@eayun.com> 1.0-1
- init version
