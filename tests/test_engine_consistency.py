import io
import json
import zipfile
from unittest.mock import patch

import numpy as np
import pytest
from fastapi import HTTPException
from PIL import Image

from core.color.cube import CubeLUT, parse_cube, serialize_leica_cube, apply_cube_to_image
from core.color.graph_compiler import compile_graph_cube, _sample_cube
from core.leica.authoritative import read_look_asset
from core.leica.compiler import compile_look_payload
from core.leica.payload import build_authoritative_payload
from server.api import studio


def graph(*nodes, **extra):
    return {'nodes': [{'id': 'input', 'type': 'input'}, *nodes,
                      {'id': 'output', 'type': 'output'}], **extra}


def identity(size=2, domain=(1., 1., 1.)):
    axis = np.linspace(0, 1, size)
    return CubeLUT('identity', size, (0., 0., 0.), domain,
                   np.array([(r, g, b) for b in axis for g in axis for r in axis], dtype=np.float32))


def test_authoritative_payload_bytes_survive_compiler_changes():
    from core.leica.authoritative import get_authoritative_look
    for look_id in range(1001, 1010):
        look = get_authoritative_look(look_id)
        payload, _ = compile_look_payload(look_id, look['name'], read_look_asset(look_id, 'icon'),
                                         read_look_asset(look_id, 'cube'), base=look['base'])
        assert payload == build_authoritative_payload(look_id)


@pytest.mark.parametrize('size', [2, 17])
def test_leica_export_preserves_nonunit_source_domain(size):
    source = identity(size, (2., 2., 2.))
    exported = parse_cube(serialize_leica_cube(source, 1142, 'Domain Test', 0))
    points = np.array([[.25, .5, .75], [1, 1, 1]], dtype=np.float32)
    np.testing.assert_allclose(_sample_cube(points, exported), _sample_cube(points, source), atol=2e-6)


@pytest.mark.parametrize('header,row', [
    ('DOMAIN_MAX 0 1 1', '0 0 0'),
    ('DOMAIN_MIN nan 0 0', '0 0 0'),
    ('DOMAIN_MIN 0 0', '0 0 0'),
    ('', 'nan 0 0'),
])
def test_invalid_cube_is_rejected(header, row):
    with pytest.raises(ValueError):
        parse_cube(('LUT_3D_SIZE 2\n' + header + '\n' + '\n'.join([row] * 8)).encode())


def test_large_identity_lut_preview_does_not_overflow_indices():
    image = Image.new('RGB', (2, 2), (80, 120, 200)); data = io.BytesIO(); image.save(data, format='PNG')
    rendered = apply_cube_to_image(data.getvalue(), identity(65))
    result = np.asarray(Image.open(io.BytesIO(rendered)))
    np.testing.assert_allclose(result[0, 0], [80, 120, 200], atol=3)


def test_disabled_missing_lut_does_not_block_other_layers():
    data, report = studio._compiled(graph({'id': 'missing', 'type': 'lut', 'enabled': False,
                                          'source_id': 'missing', 'component_id': 'cube'},
                                         {'id': 'contrast', 'type': 'contrast', 'params': {'value': .2}}))
    assert parse_cube(data).size == 17
    assert report['ready']


def test_active_unsupported_component_cannot_export_a_partial_look():
    with pytest.raises(HTTPException) as error:
        studio.build_graph_package_bytes(graph({'id': 'grain', 'type': 'grain'}, name='Incomplete', look_id=1142))
    assert error.value.status_code == 422


def test_monochrome_preview_cube_matches_export_cube():
    value = graph({'id': 'warm', 'type': 'temperature', 'params': {'value': .2}},
                  name='Mono Test', look_id=1142, base=1)
    preview, _ = studio._compiled(value)
    with zipfile.ZipFile(io.BytesIO(studio.build_graph_package_bytes(value))) as package:
        manifest = json.loads(package.read('looks_manifest.json'))
        exported = package.read(manifest[0]['cube'])
    np.testing.assert_allclose(parse_cube(preview).values, parse_cube(exported).values, atol=2e-6)


def test_hald_component_hydrates_as_lut_not_image_bytes():
    pixels = (identity(4).values.reshape(8, 8, 3) * 255).astype(np.uint8)
    data = io.BytesIO(); Image.fromarray(pixels).save(data, format='PNG')
    source = {'asset_type': 'hald', 'content': data.getvalue(), 'components': [
        {'id': 'hald_lut', 'type': 'cube_lut'}]}
    with patch.object(studio.library, 'get', return_value=source):
        compiled, report = studio._compiled(graph({'id': 'hald', 'type': 'lut', 'source_id': 'hald', 'component_id': 'hald_lut'}))
    assert report['ready']
    np.testing.assert_allclose(parse_cube(compiled).values, identity(17).values, atol=1e-5)


def test_downloaded_injector_runs_alone_and_retains_editable_graph(tmp_path):
    import subprocess
    import sys
    value = graph(name='Standalone', look_id=1142)
    with zipfile.ZipFile(io.BytesIO(studio.build_graph_package_bytes(value))) as archive:
        (tmp_path / 'injector.py').write_bytes(archive.read('injector.py'))
        assert json.loads(archive.read('look-graph.json'))['nodes'] == value['nodes']
    result = subprocess.run([sys.executable, str(tmp_path / 'injector.py'), '--list'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'VALIDATION ONLY' in result.stdout


def test_dcp_calibration_matrix_is_not_a_display_rgb_transform():
    source = {'asset_type': 'dcp', 'content': b'', 'components': [
        {'id': 'ColorMatrix1', 'type': 'matrix', 'values': [1, 0, 0, 0, 1, 0, 0, 0, 1]}]}
    with patch.object(studio.library, 'get', return_value=source), pytest.raises(HTTPException) as error:
        studio._compiled(graph({'id': 'matrix', 'type': 'matrix', 'source_id': 'dcp', 'component_id': 'ColorMatrix1'}))
    assert error.value.status_code == 422
    assert 'calibration' in str(error.value.detail)


def test_selected_pack_has_one_valid_standalone_injector(tmp_path):
    import subprocess
    import sys
    from core.leica.package import combine_look_packages
    one = studio.build_graph_package_bytes(graph(name='One', look_id=1142))
    two = studio.build_graph_package_bytes(graph(name='Two', look_id=1143, base=1))
    combined = combine_look_packages([one, two])
    assert combined == combine_look_packages([one, two])
    with zipfile.ZipFile(io.BytesIO(combined)) as archive:
        assert len(json.loads(archive.read('looks_manifest.json'))) == 2
        (tmp_path / 'injector.py').write_bytes(archive.read('injector.py'))
    run = subprocess.run([sys.executable, str(tmp_path / 'injector.py'), '--list'],
                         capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    with pytest.raises(ValueError, match='Duplicate Leica Look ID'):
        combine_look_packages([one, one])


def test_xmp_point_curve_is_extracted_instead_of_empty_component():
    from core.assets.inspect import inspect_source_asset
    source = b'''<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"><rdf:RDF><rdf:Description><crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>128, 150</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012></rdf:Description></rdf:RDF></x:xmpmeta>'''
    result = inspect_source_asset('curve.xmp', source)
    curve = next(c for c in result['components'] if c['type'] == 'tone_curve')
    np.testing.assert_allclose(curve['values'], [[0, 0], [128/255, 150/255], [1, 1]])


def test_grade_tints_neutral_pixels_with_selected_hue_and_balance_changes_mask():
    from core.color.graph_compiler import _manual_transform
    neutral = np.array([[.3, .3, .3], [.6, .6, .6]], dtype=np.float32)
    blue = _manual_transform(neutral, 'shadow_grade', {'hue': 240, 'amount': .5, 'balance': 0})
    assert blue[0, 2] > blue[0, 0]
    shifted = _manual_transform(neutral, 'shadow_grade', {'hue': 240, 'amount': .5, 'balance': .8})
    assert not np.allclose(blue, shifted)


def test_monochrome_filters_compile_and_favor_selected_color():
    data, status = studio._compiled(studio._graph({'layers': [], 'base': 'Monochrome',
        'controls': {'redFilter': 80}, 'name': 'Red Filter', 'look_id': 1142}))
    assert status['ready']
    colors = _sample_cube(np.array([[1, 0, 0], [0, 0, 1]], dtype=np.float32), parse_cube(data))
    assert colors[0, 0] > colors[1, 0]
    np.testing.assert_allclose(colors[:, 0], colors[:, 1], atol=1e-6)
