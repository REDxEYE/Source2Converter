from pathlib import Path

from SourceIO.library.utils.datamodel import load

if __name__ == '__main__':
    session_path = Path(
        r"H:\SteamLibrary\SteamApps\common\SourceFilmmaker\game\usermod\elements\sessions\hijack_output.dmx")
    session = load(session_path)
    for game_model in session.find_elements(elemtype='DmeGameModel'):
        if not game_model['modelName']:
            continue
        model_path = game_model['modelName']
        if model_path.endswith('.mdl'):
            model_path = model_path.replace('.mdl', '.vmdl')
        game_model['modelName'] = model_path
    session.write(session_path.with_name(session_path.stem + '_sfm2.dmx'), 'binary', 5)
